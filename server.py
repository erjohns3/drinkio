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
import socketserver
from enum import Enum


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
    "position": -1,
    "users": 0,
    "drink": "",
    "timer": -1,
    "progress": -1,
    "tick": 0
}

#################################################

pi = pigpio.pi()

PAN_PIN = 12
TILT_PIN = 13
PUMP_PIN = 27
FLOW_PIN = 17

FLOW_BIAS = 0.637
FLOW_MULT = 0.0203
FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 5

TILT_UP = 400000
TILT_DOWN = 500000
TILT_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 100000 # pwm change per second
PAN_PERIOD = 0.01


def signal_handler(sig, frame):
    print('Ctrl+C', flush=True)
    pi.write(PUMP_PIN, 1)
    pi.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#####################################

loc = pathlib.Path(__file__).parent.absolute()
f = open(str(loc)+"/config.json", "r")
config = json.loads(f.read())
f.close()

drinks = config["drinks"]
ports = config["ports"]
ingredients = config["ingredients"]

#####################################

pi.set_mode(PUMP_PIN, pigpio.OUTPUT)
pi.write(PUMP_PIN, 1)
pan_curr = 495000

#################################### gpio signals

flow_lock = threading.Lock()
flow_tick = 0

def flow_rise(pin, level, tick):
    global flow_tick
    flow_lock.acquire()
    flow_tick = flow_tick + 1
    flow_lock.release()
    print("flow: {}".format(flow_tick), flush=True)

pi.set_mode(FLOW_PIN, pigpio.INPUT)
pi.set_pull_up_down(FLOW_PIN, pigpio.PUD_DOWN)
pi.callback(FLOW_PIN, pigpio.RISING_EDGE, flow_rise)

####################################

cancel_lock = threading.Lock()
cancel_pour = False

clean = {
    "water": 5
}

def check_cancel():
    cancel_lock.acquire()
    if cancel_pour:
        cancel_pour = False
        cancel_lock.release()
        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        time.sleep(2)
        pi.write(PUMP_PIN, 1)
        return True
    cancel_lock.release()
    return False

async def pour_drink(drink):

    pi.write(PUMP_PIN, 0)

    for ingredient in drink:
        if check_cancel(): return
        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        config_lock.acquire()
        print("Ingredient: {}, Angle: {}, Amount: {}".format(ingredient, ports[ingredients[ingredient]["port"]], drink[ingredient]), flush=True)
        config_lock.release()
        #pi.write(PUMP_PIN, 0)
        time.sleep(2)
        pause = 7
        config_lock.acquire()
        pan_goal = ports[ingredients[ingredient]["port"]]
        config_lock.release()
        while pan_curr != pan_goal:
            if check_cancel(): return
            if pan_goal > pan_curr:
                pan_curr = min(pan_curr + (PAN_SPEED * PAN_PERIOD), pan_goal)
            else:
                pan_curr = max(pan_curr - (PAN_SPEED * PAN_PERIOD), pan_goal)
            pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
            time.sleep(PAN_PERIOD)
            pause = pause - PAN_PERIOD

        time.sleep(3 + max(pause, 0))

        flow_lock.acquire()
        flow_tick = 0
        flow_lock.release()

        elapsed = 0
        flow_prev = 0

        tilt_curr = TILT_UP
        while tilt_curr != TILT_DOWN:
            if check_cancel(): return
            tilt_curr = min(tilt_curr + (TILT_SPEED * TILT_PERIOD), TILT_DOWN)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            time.sleep(TILT_PERIOD)

        while True:
            if check_cancel(): return
            flow_lock.acquire()
            if flow_tick >= max((drink[ingredient] - FLOW_BIAS) / FLOW_MULT, 4):
                print("----done", flush=True)
                break
            
            if elapsed > 8:
                if flow_tick - flow_prev <= 3:
                    config_lock.acquire()
                    ingredients[ingredient]["empty"] = True
                    config_lock.release()
                    await broadcast_config()
                    print("----empty", flush=True)
                    break
                flow_prev = flow_tick
                elapsed = 4

            elapsed = elapsed + FLOW_PERIOD
            flow_lock.release
            time.sleep(FLOW_PERIOD)

        flow_lock.release
        #pi.write(PUMP_PIN, 1)

    pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
    time.sleep(2)
    pause = 7
    pan_goal = 500000
    while pan_curr != pan_goal:
        if check_cancel(): return
        if pan_goal > pan_curr:
            pan_curr = min(pan_curr + (PAN_SPEED * PAN_PERIOD), pan_goal)
        else:
            pan_curr = max(pan_curr - (PAN_SPEED * PAN_PERIOD), pan_goal)
        pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
        time.sleep(PAN_PERIOD)
        pause = pause - PAN_PERIOD

    time.sleep(3 + max(pause, 0))
    pi.write(PUMP_PIN, 1)

async def pour_cycle(drink):

    print("pour drink:")
    print(drink)
    await pour_drink(drink)

    cancel_lock.acquire()
    cancel_pour = False
    cancel_lock.release()

    state_lock.acquire()
    state = State.CLEANING
    print("----CLEANING----")
    state_lock.release()

    print("clean:")
    await pour_drink(clean)

    state_lock.acquire()
    state_reset()
    state_lock.release()

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

class ReuseAddrTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def http_server():
    httpd = ReuseAddrTCPServer(("", PORT), Handler)
    print("serving at port", PORT)
    httpd.serve_forever()

http_thread = threading.Thread(target=http_server, args=(), daemon=True)
http_thread.start()

#################################################
        
state = State.STANDBY
ready_wait = 20
ready_timer = False
ready_time = 0
progress = 30


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
    await socket.send('{"status":' +json.dumps(status) + '}')

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
            await websocket.send(json.dumps(config))
            i=i+1

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer

    state_lock.acquire()
    socket_list.append(websocket)
    print("add: " + websocket.remote_address[0])
    state_lock.release()
    
    await websocket.send(json.dumps(config))
    while True:
        msg_string = await websocket.recv()
        msg = json.loads(msg_string)
        print(msg)
        state_lock.acquire()
        if 'type' in msg:
            if msg['type'] == "query":
                await send_status(websocket)

            elif msg['type'] == "queue" and 'name' in msg and 'ingredients' in msg:
                print("queue add")
                if state == State.STANDBY:
                    await ready_start()
                    state = State.READY
                    print("----READY----")
                
                add_user = True
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        add_user = False
                        break
                if add_user:
                    user_queue.append(websocket.remote_address[0])
                    
                user_drink_name[websocket.remote_address[0]] = msg['name']
                user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
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
                        pour_thread = threading.Thread(target=asyncio.run, args=pour_cycle(user_drink_ingredients[user_queue[0]]), daemon=True)
                        pour_thread.start()
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
                        pour_thread = threading.Thread(target=pour_cycle, kwargs=user_drink_ingredients[user_queue[0]], daemon=True)
                        pour_thread.start()
                        await broadcast_status()

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == websocket.remote_address[0]:
                    state = State.CANCELLING
                    print("----CANCELLING----")
                    print("pour cancel")
                    cancel_lock.acquire()
                    cancel_pour = True
                    cancel_lock.release()
                    await broadcast_status()

        state_lock.release()

def pour_wrapper(arg):
    await pour_cycle(arg)

start_server = websockets.serve(init, "0.0.0.0", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
