import threading
import pigpio
import time
import sys
import json
import signal
import pathlib
import asyncio
import websockets
import http.server
from enum import Enum
import argparse
import os
from os import path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler



class State(Enum):
    STANDBY = 1
    READY = 2
    POURING = 3
    CANCELLING = 4
    CLEANING = 5

class AsyncTimer:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        self._task.cancel()

state_lock = threading.Lock()
config_lock = threading.Lock()
socket_list = []
user_queue = []
user_drink_name = {}
user_drink_ingredients = {}

status = {
    "position": False,
    "users": 0,
    "drink": False,
    "timer": False,
    "progress": False,
    "tick": 0
}

################################################# Setup pi

PAN_PIN = 12
TILT_PIN = 13
PUMP_PIN = 27
FLOW_PIN = 17

FLOW_BIAS = 0.921
FLOW_MULT = 0.0175
FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 5

TILT_UP = 400000
TILT_DOWN = 500000
TILT_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 150000 # pwm change per second
PAN_PERIOD = 0.01

flow_lock = threading.Lock()
flow_tick = 0

pi = None

def flow_rise(pin, level, tick):
    global flow_tick
    flow_lock.acquire()
    flow_tick = flow_tick + 1
    flow_lock.release()
    print("flow: {}".format(flow_tick), flush=True)

def setup_pigpio():
    global pi
    pi = pigpio.pi()

    pi.set_mode(PUMP_PIN, pigpio.OUTPUT)
    pi.write(PUMP_PIN, 1)
    pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
    pan_curr = 495000

    pi.set_mode(FLOW_PIN, pigpio.INPUT)
    pi.set_pull_up_down(FLOW_PIN, pigpio.PUD_DOWN)
    pi.callback(FLOW_PIN, pigpio.RISING_EDGE, flow_rise)



def signal_handler(sig, frame):
    print('Ctrl+C', flush=True)
    if pi is None:
        print('signal_handler skipped for testing')
    else:
        pi.write(PUMP_PIN, 1)
        pi.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#####################################

loc = pathlib.Path(__file__).parent.absolute()
drink_io_folder = str(loc)


with open(path.join(drink_io_folder, 'ingredients_owned.json'), 'r') as f:
    ingredients_owned = json.loads(f.read())['ingredients_owned']

with open(path.join(drink_io_folder, 'rasp_pi_port_config.json'), 'r') as f:
    rasp_pi_port_config = json.loads(f.read())

with open(path.join(drink_io_folder, 'abv_of_ingredients.json'), 'r') as f:
    github_ingredients = json.loads(f.read().lower())

with open(path.join(drink_io_folder, 'recipes.json'), 'rb') as f:
    github_recipes = json.loads(f.read().decode("UTF-8").lower())


class MyWatchdogMonitor(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('ingredients_owned.json'):
            print(f'event type: {event.event_type}  path : {event.src_path}')

event_handler = MyWatchdogMonitor()
observer = Observer()
observer.schedule(event_handler, path=drink_io_folder, recursive=False)
observer.start()


ports = rasp_pi_port_config['ports']

CL_CONSTANT = 0.33814

drink_dict = {}
for i in github_recipes:
    lol = []
    for word in i['name'].split():
        lol.append(word.capitalize())
    name = ' '.join(lol)

    if name not in drink_dict:
        drink_dict[name] = {}

    drink_dict[name]['ingredients'] = i['ingredients']

    for ingredient in drink_dict[name]['ingredients']:
        if 'unit' in ingredient and ingredient['unit'] == 'cl':
            ingredient['amount'] *= CL_CONSTANT
            ingredient['amount'] = round(ingredient['amount'], 1)
            ingredient['unit'] = 'oz'




formatted_github_ingredients = {}
for key, value in github_ingredients.items():
    if key in ingredients_owned:
        del value['taste']
        value['empty'] = False
        value['port'] = ingredients_owned[key]['port']
        value['abv'] /= 100
        formatted_github_ingredients[key] = value

to_remove = set()
formatted_github_drinks = {}
for key, value in drink_dict.items():
    formatted_github_drinks[key] = {}
    for ingredient in value['ingredients']:
        if 'amount' in ingredient:
            if ingredient['ingredient'] not in formatted_github_ingredients:
                to_remove.add(key)
            formatted_github_drinks[key][ingredient['ingredient']] = ingredient['amount']

for i in to_remove:
    del formatted_github_drinks[i]

to_send_to_client = {}
to_send_to_client['drinks'] = formatted_github_drinks
to_send_to_client['ingredients'] = formatted_github_ingredients
ingredients = to_send_to_client['ingredients']



####################################

cancel_lock = threading.Lock()
cancel_pour = False

clean = {
    "water": 5
}

async def check_cancel():
    if pi is None:
        print("check_cancel() skipped for testing")
        return False
    global cancel_pour

    cancel_lock.acquire()
    if cancel_pour:
        cancel_pour = False
        cancel_lock.release()
        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        await asyncio.sleep(5)
        pi.write(PUMP_PIN, 1)
        return True
    cancel_lock.release()
    return False

async def pour_drink(drink):
    if pi is None:
        print("pour_drink() skipped for testing")
        return
    global pan_curr
    global progress
    global flow_tick

    ingredient_count = len(drink)
    ingredient_index = 0

    pi.write(PUMP_PIN, 0)

    for ingredient in drink:
        if await check_cancel(): return
        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        config_lock.acquire()
        print("Ingredient: {}, Angle: {}, Amount: {}".format(ingredient, ports[ingredients[ingredient]["port"]], drink[ingredient]), flush=True)
        config_lock.release()
        
        pause = 4
        config_lock.acquire()
        pan_goal = ports[ingredients[ingredient]["port"]]
        config_lock.release()
        print("pan align: {} -> {}".format(pan_curr, pan_goal))
        while pan_curr != pan_goal:
            if await check_cancel(): return
            if pan_goal > pan_curr:
                pan_curr = min(pan_curr + (PAN_SPEED * PAN_PERIOD), pan_goal)
            else:
                pan_curr = max(pan_curr - (PAN_SPEED * PAN_PERIOD), pan_goal)
            pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
            await asyncio.sleep(PAN_PERIOD)
            pause = pause - PAN_PERIOD

        await asyncio.sleep(1 + max(pause, 0))

        state_lock.acquire()
        if state == State.POURING:
            progress = (ingredient_index + 0.5) / ingredient_count * 100
            await broadcast_status()
        state_lock.release()

        flow_lock.acquire()
        flow_tick = 0
        flow_lock.release()

        elapsed = 0
        flow_prev = 0

        tilt_curr = TILT_UP
        print("tilt down")
        while tilt_curr != TILT_DOWN:
            if await check_cancel(): return
            tilt_curr = min(tilt_curr + (TILT_SPEED * TILT_PERIOD), TILT_DOWN)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)

        flow_goal = max((drink[ingredient] - FLOW_BIAS) / FLOW_MULT, 4)
        print("flow: {} - {}".format(drink[ingredient], flow_goal))
        while True:
            if await check_cancel(): return
            flow_lock.acquire()
            if flow_tick >= flow_goal:
                print("ingredient done", flush=True)
                break
            
            if elapsed > 8:
                if flow_tick - flow_prev <= 3:
                    config_lock.acquire()
                    ingredients[ingredient]["empty"] = True
                    config_lock.release()
                    state_lock.acquire()
                    await broadcast_config()
                    state_lock.release()
                    print("ingredient empty", flush=True)
                    break
                flow_prev = flow_tick
                elapsed = 4

            elapsed = elapsed + FLOW_PERIOD
            flow_lock.release()
            await asyncio.sleep(FLOW_PERIOD)

        flow_lock.release()

        state_lock.acquire()
        if state == State.POURING:
            progress = (ingredient_index + 1.0) / ingredient_count * 100
            await broadcast_status()
        state_lock.release()

        ingredient_index = ingredient_index + 1

    print("tilt up")
    pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
    await asyncio.sleep(5)
    pi.write(PUMP_PIN, 1)

async def pour_cycle(drink):
    global state

    print("pour drink:")
    print(drink)
    await pour_drink(drink)
    print("drink done")

    await asyncio.sleep(5)

    state_lock.acquire()
    state = State.CLEANING
    print("----CLEANING----")
    await broadcast_status()
    state_lock.release()

    cancel_lock.acquire()
    cancel_pour = False
    cancel_lock.release()

    print("pour clean:")
    print(clean)
    await pour_drink(clean)
    print("clean done")

    state_lock.acquire()
    await state_reset()
    state_lock.release()

#################################################

PORT = 8000
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join('frontend'), **kwargs)
        
def http_server(testing):
    httpd = http.server.ThreadingHTTPServer(("", PORT), Handler)
    print("serving at port", PORT)
    httpd.serve_forever()


#################################################

state = State.STANDBY
ready_wait = 20
ready_timer = False
ready_time = 0
progress = 0


async def ready_start():
    global ready_timer
    global ready_time

    ready_timer = AsyncTimer(ready_wait, ready_end)
    ready_time = time.time()


async def ready_end():
    state_lock.acquire()
    await state_reset()
    state_lock.release()

async def state_reset():
    global state
    global user_queue

    user_queue.pop(0)
    if len(user_queue) == 0:
        state = State.STANDBY
        print("----STANDBY----")
    else:
        state = State.READY
        print("----READY----")
        await ready_start()
    await broadcast_status()

async def send_status(socket):
    global status

    i = 1
    found = False
    for user in user_queue:
        if user == socket.remote_address[0]:
            found = True
            break
        i = i+1
    if found:
        status["position"] = i
        status["drink"] = user_drink_name[user]
        if state == State.READY and user_queue[0] == socket.remote_address[0]:
            status["timer"] = max(0, ready_time + ready_wait - time.time())
            status["progress"] = False
        elif state == State.POURING and user_queue[0] == socket.remote_address[0]:
            status["timer"] = False
            status["progress"] = progress
        else:
            status["timer"] = False
            status["progress"] = False
    else:
        status["position"] = False
        status["drink"] = False
        status["timer"] = False
        status["progress"] = False
    status["tick"] = status["tick"] + 1
    status["users"] = len(user_queue)
    print(status)
    try:
        await socket.send('{"status":' +json.dumps(status) + '}')
    except:
        print("socket send failed")

async def broadcast_status():
    global socket_list
    
    i=0
    while i < len(socket_list):
        if socket_list[i].closed:
            socket_list.pop(i)
        else:
            await send_status(socket_list[i])
            i=i+1

async def broadcast_config():
    global socket_list
    
    i=0
    while i < len(socket_list):
        if socket_list[i].closed:
            socket_list.pop(i)
        else:
            await socket_list[i].send(json.dumps(to_send_to_client))
            i=i+1

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer
    global cancel_pour
    global progress

    state_lock.acquire()
    socket_list.append(websocket)
    print("add: " + websocket.remote_address[0])
    state_lock.release()
    
    await websocket.send(json.dumps(to_send_to_client))
    while True:
        try:
            msg_string = await websocket.recv()
        except:
            print("socket recv failed")
            break
        msg = json.loads(msg_string)
        print(msg)
        state_lock.acquire()
        if 'type' in msg:
            if msg['type'] == "query":
                await send_status(websocket)

            elif msg['type'] == "queue" and 'name' in msg and 'ingredients' in msg:
                print("queue add")
                
                add_user = True
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        add_user = False
                        break
                if add_user:
                    user_queue.append(websocket.remote_address[0])
                    
                user_drink_name[websocket.remote_address[0]] = msg['name']
                user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']

                if state == State.STANDBY:
                    state = State.READY
                    print("----READY----")
                    await ready_start()

                await broadcast_status()
            
            elif msg['type'] == "remove":
                found = False
                i = 0
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        found = True
                        break
                    i = i+1
                if found:
                    if i > 0:
                        user_queue.remove(websocket.remote_address[0])
                        await broadcast_status()
                    elif state == State.READY:
                        ready_timer.cancel()
                        await state_reset()

            elif msg['type'] == "pour" and 'name' in msg and 'ingredients' in msg:
                if state == State.STANDBY:
                    full = True
                    config_lock.acquire()
                    for ingredient in msg['ingredients']:
                        if ingredients[ingredient]["empty"]:
                            full = False
                    config_lock.release()
                    if full:
                        user_queue.append(websocket.remote_address[0])
                        user_drink_name[websocket.remote_address[0]] = msg['name']
                        user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                        state = State.POURING
                        print("----POURING----")
                        print("pour now")
                        #pour_thread = threading.Thread(target=asyncio.run, args=pour_cycle(user_drink_ingredients[user_queue[0]]), daemon=True)
                        #pour_thread.start()
                        asyncio.create_task(pour_cycle(user_drink_ingredients[user_queue[0]]))
                        progress = 0
                        await broadcast_status()

            elif msg['type'] == "pour" :
                if state == State.READY and user_queue[0] == websocket.remote_address[0] and user_queue[0] in user_drink_ingredients:
                    full = True
                    config_lock.acquire()
                    for ingredient in user_drink_ingredients[user_queue[0]]:
                        if ingredients[ingredient]["empty"]:
                            full = False
                    config_lock.release()
                    if full:
                        ready_timer.cancel()
                        state = State.POURING
                        print("----POURING----")
                        print("pour queue")
                        asyncio.create_task(pour_cycle(user_drink_ingredients[user_queue[0]]))
                        progress = 0
                        await broadcast_status()

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == websocket.remote_address[0]:
                    state = State.CANCELLING
                    print("----CANCELLING----")
                    print("pour cancel")
                    cancel_lock.acquire()
                    cancel_pour = True
                    cancel_lock.release()
                    user_queue[0] = "cancelled"
                    await broadcast_status()

        state_lock.release()

def run_asyncio():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    start_server = websockets.serve(init, "192.168.86.58", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--testing', action='store_true', default=False,
                   help='To run webserver without drinkmaker attached')
    args = parser.parse_args()

    if not args.testing:
        setup_pigpio()

    http_thread = threading.Thread(target=http_server, args=[args.testing], daemon=True)
    http_thread.start()

    run_asyncio()



if __name__ == "__main__":
    main()
