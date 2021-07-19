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

state_lock = threading.Lock()
user_queue = []
user_drink_name = {}
user_drink_ingredients = {}

status = {
    "position": -1,
    "users": 0,
    "drink": "",
    "timer": -1,
    "progress": -1
}

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

def http_server():
    httpd = socketserver.TCPServer(("", PORT), Handler)
    print("serving at port", PORT)
    httpd.serve_forever()

http_thread = threading.Thread(target=http_server, args=(), daemon=True)
http_thread.start()

#################################################
        
state = State.STANDBY
ready_wait = 30
ready_timer = False
ready_time = 0
progress = 30


def ready_start():
    global ready_timer
    global ready_time

    ready_timer = threading.Timer(ready_wait, ready_end)
    ready_timer.start()
    ready_time = time.time()


def ready_end():
    state_lock.acquire()
    state_reset()
    state_lock.release()

def state_reset():
    global state
    global user_queue

    user_queue.pop()
    if len(user_queue) == 0:
        state = State.STANDBY
    else:
        state = State.READY
        ready_start()

async def send_status(websocket):
    global state
    global user_queue
    global ready_time
    global status

    i = 1
    found = False
    for user in user_queue:
        if user == websocket.remote_address[0]:
            found = True
            break
        i = i+1
    if found:
        status["position"] = i
        status["drink"] = user_drink_name[user]
        if state == State.READY and user_queue[0] == websocket.remote_address[0]:
            status["timer"] = max(0, ready_time + ready_wait - time.time())
            status["progress"] = False
        elif state == State.POURING and user_queue[0] == websocket.remote_address[0]:
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
    status["users"] = len(user_queue)
    await websocket.send('{"status":' +json.dumps(status) + '}')

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer

    print("socket start: " + websocket.remote_address[0])
    await websocket.send(config)
    while True:
        msg_string = await websocket.recv()
        msg = json.loads(msg_string)
        print(msg)
        state_lock.acquire()
        if 'type' in msg:
            if msg['type'] == "query":
                await send_status(websocket)

            elif msg['type'] == "queue" and 'drink' in msg:
                if state == State.STANDBY:
                    ready_start()
                    state = State.READY
                
                add_user = True
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        add_user = False
                        break
                if add_user:
                    user_queue.append(websocket.remote_address[0])
                    
                user_drink_name[websocket.remote_address[0]] = msg['name']
                user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                await send_status(websocket)
            
            elif msg['type'] == "remove":
                if user_queue[0] != websocket.remote_address[0]:
                    user_queue.remove(websocket.remote_address[0])
                elif state == State.READY:
                    ready_timer.cancel()
                    state_reset()
                    
                await send_status(websocket)

            elif msg['type'] == "pour":
                print("pour start")
                if state == State.READY and user_queue[0] == websocket.remote_address[0]:
                    ready_timer.cancel()
                    state = State.POURING
                    pour_thread = threading.Thread(target=pour_cycle, args=(user_drink_ingredients[user_queue[0]]), daemon=True)
                    pour_thread.start()
                elif state == State.STANDBY and 'drink' in msg:
                    user_queue.append(websocket.remote_address[0])
                    user_drink_name[websocket.remote_address[0]] = msg['name']
                    user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                    state = State.POURING
                    pour_thread = threading.Thread(target=pour_cycle, args=(user_drink_ingredients[user_queue[0]]), daemon=True)
                    pour_thread.start()
                await send_status(websocket)
                

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == websocket.remote_address[0]:
                    state = State.CANCELLING
                    cancel_lock.acquire()
                    cancel_pour = True
                    cancel_lock.release()
                    await send_status(websocket)

        state_lock.release()

start_server = websockets.serve(init, "0.0.0.0", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

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

def pour_drink(drink):

    pi.write(PUMP_PIN, 0)

    for ingredient in drink:
        if check_cancel(): return
        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        print("Drink: {}, Angle: {}, Amount: {}".format(ingredient, ports[ingredients[ingredient]["port"]], drink[ingredient]), flush=True)
        #pi.write(PUMP_PIN, 0)
        time.sleep(2)
        pause = 7
        pan_goal = ports[ingredients[ingredient]["port"]]
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
                    ingredients[ingredient]["empty"] = True
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

def pour_cycle(drink):

    pour_drink(drink)

    cancel_lock.acquire()
    cancel_pour = False
    cancel_lock.release()

    state_lock.acquire()
    state = State.CLEANING
    state_lock.release()

    pour_drink(clean)

    state_lock.acquire()
    state_reset()
    state_lock.release()
