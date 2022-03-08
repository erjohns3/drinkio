import threading
from types import new_class
import pigpio
import time
import sys
import json
import signal
import pathlib
import asyncio
import websockets
import http.server
import tracking
import subprocess
import vlc
from omxplayer.player import OMXPlayer
from enum import Enum
import argparse
from flow_tick_helper import amount_to_flow_ticks
import os
from os import path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class State(Enum):
    UNWATCHED = 0
    STANDBY = 1
    QUEUED = 2
    POURING = 3
    CANCELLING = 4
    FINISHED = 5
    CLEANING = 6

clear_time = {
    "basement": 10,
    "hottub": 100
}

def get_drinks(uuid):
    drinks = users[uuid]['drinks']
    sum = 0
    while len(drinks) > 0 and drinks[0]['time'] < time.time() - 43200:
        drinks.pop(0)
    for drink in drinks:
        sum += drink['amount']
    return sum

def get_bac(uuid):
    user = users[uuid]
    # bac = (1 mg of alcohol) / (100 ml of blood)
    if len(user['drinks']) > 0 and user['weight'] > 0:
        if user['sex'] == "male":
            blood = user['weight'] * 0.453592 * 75
        elif user['sex'] == "female":
            blood = user['weight'] * 0.453592 * 65
        else:
            return 0

        drinks = user['drinks']
        #alcohol_mult = 17.74 # ml of alcohol per drink
        alcohol_mult = 14 # grams of alcohol per drink
        alcohol = drinks[0]['amount'] * alcohol_mult

        for i in range(1, len(drinks)):
            alcohol -= (0.015 * (blood / 10) * ((drinks[i]['time']-drinks[i-1]['time'])/3600))
            if alcohol < 0:
                alcohol = 0
            alcohol += drinks[i]['amount'] * alcohol_mult
            
        alcohol -= (0.015 * (blood / 10) * ((time.time()-drinks[len(drinks)-1]['time'])/3600))

        if alcohol < 0:
            alcohol = 0

        bac = alcohol / (blood / 10)
        return bac
    else:
        return 0

def add_drink(uuid, amount):
    users[uuid]['drinks'].append({'amount': amount, 'time': time.time()})
    print("add drink")

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
connection_list = []
queue = []
users = {}
drinks = {}
ingredients = {}
song = vlc.MediaPlayer()
video_once = vlc.MediaPlayer()
video_loop = False
args = False

################################################# Setup pi

VALVE_PIN = 6

PAN_PIN = 12
TILT_PIN = 13

ENABLE_PIN = 22
PUMP_PIN = 27
PUMP_FREQ = 320
PUMP_CAL = 1043.17710018 / PUMP_FREQ

FLOW_PIN = 17
FLOW_PERIOD = 0.005
FLOW_TIMEOUT = 15

TILT_UP = 400000
TILT_DOWN = 485000
TILT_DOWN_SPEED = 50000 # pwm change per second
TILT_UP_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 100000 # pwm change per second
PAN_PERIOD = 0.01

pan_curr = 495000
tilt_curr = TILT_UP

pi = None

TRIGGER_PIN = 23
ECHO_PIN = 24

trigger_start = 0
cup = True

dirty = False

def echo(pin, level, tick):
    global trigger_start
    global cup
    if level == 1:
        trigger_start = tick
    elif level == 0:
        distance = pigpio.tickDiff(trigger_start, tick)
        if distance > 50 and distance < 1200:
            cup = True
        else:
            cup = False

##########################################

light_task = False

async def set_state(new_state):
    global state
    global light_task

    print("state: " + str(new_state))
    old_state = state
    state = new_state

    await broadcast_status()

    # if light_task:
    #     light_task.cancel()
    # light_task = asyncio.create_task(light())

    # asyncio.create_task(buzzer(old_state, new_state))

    #video(old_state, new_state)

####################################

RED_PIN = 9
GREEN_PIN = 10
BLUE_PIN = 11

async def light():

    tick = 0

    pi.set_PWM_dutycycle(RED_PIN, 0)
    pi.set_PWM_dutycycle(GREEN_PIN, 0)
    pi.set_PWM_dutycycle(BLUE_PIN, 0)   

    if state == State.STANDBY:
        while True:
            val = int(tick if (tick <= 100) else (200 - tick))
            pi.set_PWM_dutycycle(RED_PIN, (0.8*val + 20))
            pi.set_PWM_dutycycle(GREEN_PIN, (0.8*val + 20))
            pi.set_PWM_dutycycle(BLUE_PIN, (0.8*val + 20))
            tick = (tick + 5) % 200
            await asyncio.sleep(0.05)            
        
    elif state == State.QUEUED:
        while True:
            val = int(tick if (tick <= 100) else (200 - tick))
            pi.set_PWM_dutycycle(RED_PIN, val)
            pi.set_PWM_dutycycle(BLUE_PIN, val)
            tick = (tick + 10) % 200
            await asyncio.sleep(0.05)
        
    elif state == State.POURING:
        while True:
            val = int(tick if (tick <= 100) else (200 - tick))
            pi.set_PWM_dutycycle(GREEN_PIN, (0.5*val + 50)*0.2)
            pi.set_PWM_dutycycle(BLUE_PIN, (0.5*val + 50))
            tick = (tick + 25) % 200
            await asyncio.sleep(0.02604)
        
    elif state == State.CANCELLING:
        while True:
            val = tick
            pi.set_PWM_dutycycle(RED_PIN, val)
            tick = 100 - tick
            await asyncio.sleep(0.15)

    elif state == State.FINISHED:
        while True:
            val = int(tick if (tick <= 100) else (200 - tick))
            pi.set_PWM_dutycycle(GREEN_PIN, val)
            tick = (tick + 10) % 200
            await asyncio.sleep(0.05)

    elif state == State.CLEANING:
        while True:
            val = tick
            pi.set_PWM_dutycycle(RED_PIN, val)
            pi.set_PWM_dutycycle(GREEN_PIN, val*0.06)
            tick = 100 - tick
            await asyncio.sleep(0.15)
    
######################################

BUZZ_PIN = 5

async def buzzer(old_state, new_state):

    if new_state == State.UNWATCHED:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 800)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)

    if new_state == State.STANDBY:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 800)
        await asyncio.sleep(0.2)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)
        
    elif new_state == State.QUEUED:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 1000)
        await asyncio.sleep(0.2)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)
        
    elif new_state == State.POURING:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 800)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 1000)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 800)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 400)
        await asyncio.sleep(0.5)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)
        
    elif new_state == State.CANCELLING:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.2)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)

    elif new_state == State.FINISHED:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.25)
        pi.set_PWM_frequency(BUZZ_PIN, 1000)
        await asyncio.sleep(0.25)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.25)
        pi.set_PWM_frequency(BUZZ_PIN, 1000)
        await asyncio.sleep(0.25)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)

    elif new_state == State.CLEANING:
        pi.set_PWM_dutycycle(BUZZ_PIN, 50)

        pi.set_PWM_frequency(BUZZ_PIN, 1000)
        await asyncio.sleep(0.25)
        pi.set_PWM_frequency(BUZZ_PIN, 750)
        await asyncio.sleep(0.25)
        pi.set_PWM_frequency(BUZZ_PIN, 500)
        await asyncio.sleep(0.25)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)
    
def video(old_state, new_state):

    video_once.stop()
    video_once = vlc.MediaPlayer("video/make.mp4")
    video_once.play()

    video_loop = OMXPlayer('video/idle.mp4', '--loop')
    video_loop.quit()

#######################################

def speak(text):
    subprocess.Popen(['espeak', '-s', '80', text])


def setup_pigpio():
    global pi
    pi = pigpio.pi()
    if not pi.connected:
        exit()

    pi.set_PWM_frequency(PUMP_PIN, PUMP_FREQ)
    pi.set_PWM_dutycycle(PUMP_PIN, 0)

    pi.set_mode(ENABLE_PIN, pigpio.OUTPUT)
    pi.write(ENABLE_PIN, 1)

    pi.set_mode(VALVE_PIN, pigpio.OUTPUT)
    pi.write(VALVE_PIN, 1)

    pi.set_mode(FLOW_PIN, pigpio.INPUT)
    pi.set_pull_up_down(FLOW_PIN, pigpio.PUD_OFF)

    pi.set_mode(ECHO_PIN, pigpio.INPUT)
    pi.set_pull_up_down(ECHO_PIN, pigpio.PUD_OFF)
    pi.callback(ECHO_PIN, pigpio.EITHER_EDGE, echo)

    pi.set_mode(TRIGGER_PIN, pigpio.OUTPUT)
    pi.write(TRIGGER_PIN, 0)

    pi.set_mode(RED_PIN, pigpio.OUTPUT)
    pi.set_mode(GREEN_PIN, pigpio.OUTPUT)
    pi.set_mode(BLUE_PIN, pigpio.OUTPUT)

    pi.set_PWM_dutycycle(RED_PIN, 0)
    pi.set_PWM_dutycycle(GREEN_PIN, 0)
    pi.set_PWM_dutycycle(BLUE_PIN, 0)

    pi.set_PWM_frequency(RED_PIN, 1000)
    pi.set_PWM_frequency(GREEN_PIN, 1000)
    pi.set_PWM_frequency(BLUE_PIN, 1000)

    pi.set_mode(BUZZ_PIN, pigpio.OUTPUT)
    pi.set_PWM_dutycycle(BUZZ_PIN, 0)


def signal_handler(sig, frame):
    print('SIG Handler: ' + str(sig), flush=True)
    if pi is None:
        print('signal_handler skipped for testing', flush=True)
    else:
        pi.set_PWM_dutycycle(PUMP_PIN, 0)
        pi.write(ENABLE_PIN, 1)

        pi.write(VALVE_PIN, 1)
        
        pi.set_PWM_dutycycle(RED_PIN, 0)
        pi.set_PWM_dutycycle(GREEN_PIN, 0)
        pi.set_PWM_dutycycle(BLUE_PIN, 0)

        pi.set_PWM_dutycycle(BUZZ_PIN, 0)

        pi.stop()

    tracking.DB.backup_db()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

#####################################

loc = pathlib.Path(__file__).parent.absolute()
drink_io_folder = str(loc)

with open(path.join(drink_io_folder, 'ports.json'), 'r') as f:
    ports = json.loads(f.read())

def load_config():
    config_lock.acquire()

    global drinks
    global ingredients
    global songs
    global users

    with open(path.join(drink_io_folder, 'ingredients.json'), 'r') as f:
        ingredients = json.loads(f.read())

    with open(path.join(drink_io_folder, 'recipes.json'), 'r') as f:
        drinks = json.loads(f.read())

    with open(path.join(drink_io_folder, 'songs.json'), 'r') as f:
        songs = json.loads(f.read())

    with open(path.join(drink_io_folder, 'users.json'), 'r') as f:
        users = json.loads(f.read())

    config_lock.release()

# helper functions
    
def sort_ingredients():
    global ingredients
    ingredients_sorted = {}
    # for k, v in ingredients.values():
    for k in sorted(list(ingredients.keys()), key = lambda x: ingredients[x]['port']):
        v = ingredients[k]
        ingredients_sorted[k] = v.copy()
    ingredients = ingredients_sorted

def save_ingredients():
    print("----save ingredients start----", flush=True)
    with open(path.join(drink_io_folder, 'ingredients.json'), 'w') as f:
        json.dump(ingredients, f, indent=2)
        print("----save ingredients done----", flush=True)

def save_users():
    print("----save user start----", flush=True)
    with open(path.join(drink_io_folder, 'users.json'), 'w') as f:
        json.dump(users, f, indent=2)
        print("----save user done----", flush=True)


class MyWatchdogMonitor(FileSystemEventHandler):
    def __init__(self, _config_lock, f_load_config_from_files):
        self.file_to_watch = 'ingredients.json'
        self.config_lock = _config_lock
        self.f_load_config_from_files = f_load_config_from_files
        
    def on_modified(self, event):
        if event.src_path.endswith(self.file_to_watch):
            print('{} has been changed, refreshing config with up to date values'.format(self.file_to_watch), flush=True)
            self.f_load_config_from_files(self.config_lock)

#event_handler = MyWatchdogMonitor(config_lock, load_config_from_files)
#observer = Observer()
#observer.schedule(event_handler, path=drink_io_folder, recursive=False)
#observer.start()

load_config()
sort_ingredients()
save_ingredients()

cancel_lock = threading.Lock()
cancel_pour = False

clean = {
    "water": 3
}

async def check_cancel():
    if pi is None:
        return False
    global cancel_pour
    global tilt_curr

    cancel_lock.acquire()
    if cancel_pour:
        cancel_pour = False
        cancel_lock.release()
        
        while tilt_curr != TILT_UP:
            tilt_curr = max(tilt_curr - (TILT_UP_SPEED * TILT_PERIOD), TILT_UP)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)
        print("tilt up", flush=True)
        
        await asyncio.sleep(1)

        pi.set_PWM_dutycycle(PUMP_PIN, 0)
        pi.write(ENABLE_PIN, 1)
        
        return True
    cancel_lock.release()
    return False

async def pour_drink(drink, outlet):
    if pi is None:
        print("pour_drink() skipped for testing", flush=True)
        return
    global pan_curr
    global tilt_curr
    global progress
    global ingredients
    global dirty

    ingredient_count = 0
    ingredient_index = 0
    for ingredient in drink:
        if drink[ingredient] > 0:
            ingredient_count += 1

    if outlet == 'basement':
        pi.write(VALVE_PIN, 1)
        print("outlet: basement")
    elif outlet == 'hottub':
        pi.write(VALVE_PIN, 0)
        print("outlet: hot tub")

    pi.write(ENABLE_PIN, 0)

    for ingredient in drink:
        if await check_cancel(): return

        if drink[ingredient] <= 0: continue
        
        config_lock.acquire()
        pan_goal = ports[ingredients[ingredient]["port"]]
        print("Ingredient: {}, Angle: {}, Amount: {}".format(ingredient, ports[ingredients[ingredient]["port"]], drink[ingredient]), flush=True)
        print("pan align: {} -> {}".format(pan_curr, pan_goal), flush=True)
        config_lock.release()

        await asyncio.sleep(1)

        pause = 2
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
            progress = (ingredient_index) / ingredient_count * 100 + 2
            await broadcast_status()
        state_lock.release()

        pi.set_PWM_dutycycle(PUMP_PIN, 0)

        flow_time = (drink[ingredient] + 0.581) / 0.256
        print("pump time: {} - {}".format(drink[ingredient], flow_time), flush=True)

        print("tilt down", flush=True)
        while tilt_curr != TILT_DOWN:
            if await check_cancel(): return
            tilt_curr = min(tilt_curr + (TILT_DOWN_SPEED * TILT_PERIOD), TILT_DOWN)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)

        pi.set_PWM_dutycycle(PUMP_PIN, 50)
        flow_start = time.time()
        elapsed = 0
        dirty = True

        while True:
            if await check_cancel(): return

            #flow = pi.read(FLOW_PIN) == 1
            # if flow and not flow_start:
            #     flow_start = time.time()
            #     print("flowing: " + str(elapsed))

            if time.time() >= flow_start + flow_time:
                break
            
            # if (elapsed > FLOW_TIMEOUT and not flow_start) or (not flow and flow_start):
            #     print("ingredient empty")
            #     config_lock.acquire()
            #     ingredients[ingredient]["empty"] = True
            #     save_ingredients()
            #     config_lock.release()
            #     state_lock.acquire()
            #     await broadcast_config()
            #     state_lock.release()
            #     break

            elapsed = elapsed + FLOW_PERIOD
            await asyncio.sleep(FLOW_PERIOD)

        pi.set_PWM_dutycycle(PUMP_PIN, 0)

        while tilt_curr != TILT_UP:
            tilt_curr = max(tilt_curr - (TILT_UP_SPEED * TILT_PERIOD), TILT_UP)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)

        print("tilt up done", flush=True)

        pi.set_PWM_dutycycle(PUMP_PIN, 50)

        state_lock.acquire()
        if state == State.POURING:
            progress = (ingredient_index + 0.5) / ingredient_count * 100
            await broadcast_status()
        state_lock.release()

        ingredient_index += 1

    await asyncio.sleep(clear_time[outlet])
    pi.set_PWM_dutycycle(PUMP_PIN, 0)
    pi.write(ENABLE_PIN, 1)

    state_lock.acquire()
    if state == State.POURING:
        progress = (ingredient_index) / ingredient_count * 100
        await broadcast_status()
    state_lock.release()


async def pour_cycle(drink_name, ingredient_list, outlet):
    global cancel_pour
    global song
    global video_once
    global cup
    global dirty

    #################################
    song.stop()
    print(songs, flush=True)
    print(drink_name, flush=True)
    if drink_name in songs:
        song = vlc.MediaPlayer("songs/"+songs[drink_name]+".mp4")
        print("playing custom", flush=True)
    else:
        song = vlc.MediaPlayer("songs/luigi.mp4")
        print("playing default", flush=True)
    song.play()
    ##############################

    print("pour drink:", flush=True)
    print(ingredient_list, flush=True)
    #await pour_drink(ingredient_list, outlet)
    await asyncio.sleep(10)
    print("drink done", flush=True)
    song.stop()

    if dirty:
        state_lock.acquire()
        await set_state(State.FINISHED)
        state_lock.release()

        if outlet == 'basement':
            print("waiting for cup remove...")
            cup = True
            timeout = 0
            while cup and timeout < 180:
                pi.gpio_trigger(TRIGGER_PIN, 10, 1)
                timeout += 0.5
                await asyncio.sleep(0.5)
                
            print("cup removed")

        state_lock.acquire()
        await set_state(State.CLEANING)
        state_lock.release()

        cancel_lock.acquire()
        cancel_pour = False
        cancel_lock.release()

        print("pour clean:")
        print(clean, flush=True)
        await pour_drink(clean, outlet)
        print("clean done", flush=True)

        dirty = False

    state_lock.acquire()
    await state_reset()
    state_lock.release()

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

def http_server(testing=False):
    httpd = http.server.ThreadingHTTPServer(("", PORT), Handler)
    print("serving at port " + str(PORT), flush=True)
    httpd.serve_forever()


#################################################

state = State.UNWATCHED
ready_wait = 20
ready_timer = False
ready_time = 0
progress = 1


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
    global queue

    queue.pop(0)
    if len(queue) > 0:
        await ready_start()
        await set_state(State.QUEUED)
    elif watchers > 0:
        await set_state(State.STANDBY)
    else:
        await set_state(State.UNWATCHED)

# userState = NOLINE, OUTLINE, INLINE, FRONTLINE, POURING
async def send_status(socket, uuid):
    status = {}

    if state == State.UNWATCHED or state == State.STANDBY:
        status["userState"] = "NOLINE"
    else:
        status["userState"] = "OUTLINE"

    for i in range(0, len(queue)):
        if queue[i] == uuid:
            status["position"] = i+1
            if i == 0:
                if state == State.QUEUED:
                    status["userState"] = "FRONTLINE"
                    status["timer"] = max(0, ready_time + ready_wait - time.time())
                elif state == State.POURING:
                    status["userState"] = "POURING"
                    status["progress"] = progress
            else:
                status["userState"] = "INLINE"
            break

    status["size"] = len(queue)
    status["makerState"] = state.name
    message = {
        'status': status
    }
    dump = json.dumps(message)
    try:
        await socket.send(dump)
    except:
        print("socket send failed", flush=True)

async def broadcast_status():
    for connection in connection_list:
        if connection['uuid'] is not False:
            await send_status(connection['socket'], connection['uuid'])


async def broadcast_config():
    for connection in connection_list:
        config_lock.acquire()
        message = {
            'drinks': drinks,
            'ingredients': ingredients
        }
        dump = json.dumps(message)
        config_lock.release()
        try:
            await connection['socket'].send(dump)
        except:
            print("socket send failed", flush=True)


async def send_user(socket, uuid):
    user = users[uuid]
    drinks = get_drinks(uuid)
    bac = get_bac(uuid)
    message = {
        'user': {
            'name': user['name'],
            'weight': user['weight'],
            'sex': user['sex'],
            'drinks': drinks,
            'bac': bac
        }
    }
    dump = json.dumps(message)
    try:
        await socket.send(dump)
    except:
        print("socket send failed", flush=True)

watchers = 0

async def watched():
    if state == State.UNWATCHED:
        await set_state(State.STANDBY)
    print("first watching user on")

async def unwatched():
    if state == State.STANDBY:
        await set_state(State.UNWATCHED)
    print("last watching user off")

#################################################

async def init(websocket, path):
    global state
    global queue
    global ready_timer
    global cancel_pour
    global progress
    global ingredients
    global watchers

    state_lock.acquire()
    if len(connection_list) == 0:
        print("first user on")
    
    connection_list.append({'socket': websocket, 'uuid': False, 'watching': True})
    print("init - " + websocket.remote_address[0] + " : " + str(websocket.remote_address[1]), flush=True)
    watchers += 1
    print("watchers: " + str(watchers))
    if watchers == 1:
        await watched()
    state_lock.release()
    
    config_lock.acquire()
    message = {
        'drinks': drinks,
        'ingredients': ingredients
    }
    dump = json.dumps(message)
    config_lock.release()
    try:
        await websocket.send(dump)
    except:
        print("socket send failed", flush=True)
    while True:
        try:
            msg_string = await websocket.recv()
        except:
            print("socket recv FAILED - " + websocket.remote_address[0] + " : " + str(websocket.remote_address[1]), flush=True)
            state_lock.acquire()
            i=0
            while i < len(connection_list):
                if connection_list[i]['socket'] == websocket:
                    if len(connection_list) == 1:
                        print("last user off")
                    if connection_list[i]['watching'] == True:
                        watchers -= 1
                        print("watchers: " + str(watchers))
                        if watchers == 0:
                            await unwatched()
                    connection_list.pop(i)
                    break
                i += 1
            state_lock.release()
            break
        print("socket recv - " + websocket.remote_address[0] + " : " + str(websocket.remote_address[1]), flush=True)
        msg = json.loads(msg_string)
        print(msg, flush=True)
        state_lock.acquire()
        if 'type' in msg and 'uuid' in msg:
            if msg['type'] == "query":
                for connection in connection_list:
                    if connection['socket'] == websocket:
                        if msg['uuid'] in users:
                            print("existing user: " + users[msg['uuid']]['name'])
                            await send_user(websocket, msg['uuid'])
                        else:
                            print("new user")
                            users[msg['uuid']] = {
                                'name': "",
                                'weight': 0,
                                'sex': "",
                                'drinks': [],
                                'admin': False
                            }
                        connection['uuid'] = msg['uuid']
                        break
                await send_status(websocket, msg['uuid'])

            elif msg['type'] == "visible":
                for connection in connection_list:
                    if connection['socket'] == websocket and connection['watching'] == False:
                        connection['watching'] = True
                        watchers += 1
                        print("watchers: " + str(watchers))
                        if watchers == 1:
                            await watched()

            elif msg['type'] == "hidden":
                print("hidden")
                for connection in connection_list:
                    if connection['socket'] == websocket and connection['watching'] == True:
                        connection['watching'] = False
                        watchers -= 1
                        print("watchers: " + str(watchers))
                        if watchers == 0:
                            await unwatched()

            elif args.local and websocket.remote_address[0] != "192.168.86.1" and not users[msg['uuid']]['admin']:
                print("non local, uer blocked from commands", flush=True)

            elif msg['type'] == "user" and 'name' in msg and 'weight' in msg and 'sex' in msg:

                users[msg['uuid']]['name'] = msg['name']
                try:
                    weight = float(msg['weight'])
                except:
                    weight = 0
                users[msg['uuid']]['weight'] = weight
                users[msg['uuid']]['sex'] = msg['sex']
                await send_user(websocket, msg['uuid'])
                save_users()

            elif msg['type'] == "ingredient" and 'ingredient' in msg and 'empty' in msg:
                if users[msg['uuid']]['admin']:
                    print(msg['ingredient'] + " empty: "+msg['uuid'], flush=True)
                    config_lock.acquire()
                    ingredients[msg['ingredient']]["empty"] = msg['empty']
                    save_ingredients()
                    config_lock.release()
                    await broadcast_config()                    

            elif msg['type'] == "queue":
                print("queue add", flush=True)
                
                if state == State.UNWATCHED or state == State.STANDBY:
                    queue.append(msg['uuid'])
                    await ready_start()
                    await set_state(State.QUEUED)
                elif state == State.QUEUED:
                    add_queue = True
                    for i in range(0, len(queue)):
                        if queue[i] == msg['uuid']:
                            add_queue = False
                            break
                    if add_queue:
                        queue.append(msg['uuid'])
                        await broadcast_status()
                else:
                    add_queue = True
                    for i in range(1, len(queue)):
                        if queue[i] == msg['uuid']:
                            add_queue = False
                            break
                    if add_queue:
                        queue.append(msg['uuid'])
                        await broadcast_status()

            elif msg['type'] == "remove":
                print("queue remove", flush=True)
                for i in range(0, len(queue)):
                    if queue[i] == msg['uuid']:
                        if i > 0:
                            queue.pop(i)
                            await broadcast_status()
                        elif state == State.QUEUED:
                            ready_timer.cancel()
                            await state_reset()
                        break

            elif msg['type'] == "pour" and 'name' in msg and 'ingredients' in msg and 'outlet' in msg:
                
                pour = False
                if state == State.UNWATCHED or state == State.STANDBY:
                    queue.append(msg['uuid'])
                    pour = True
                elif state == State.QUEUED:
                    for i in range(0, len(queue)):
                        if queue[i] == msg['uuid']:
                            ready_timer.cancel()
                            pour = True
                            break
                if pour:
                    full = True
                    alcohol = 0
                    config_lock.acquire()
                    for ingredient in msg['ingredients']:
                        alcohol += msg['ingredients'][ingredient] * ingredients[ingredient]['abv'] / 0.6
                        if ingredients[ingredient]["empty"]:
                            full = False
                    config_lock.release()
                    if full:
                        tracking.DB.record_pour(msg['uuid'], msg['name'], msg['ingredients'])
                        progress = 1
                        await set_state(State.POURING)
                        asyncio.create_task(pour_cycle(msg['name'], msg['ingredients'], msg['outlet']))
                        add_drink(msg['uuid'], alcohol)
                        await send_user(websocket, msg['uuid'])

            elif msg['type'] == "cancel":
                if state == State.POURING and queue[0] == msg['uuid']:
                    cancel_lock.acquire()
                    cancel_pour = True
                    cancel_lock.release()
                    queue[0] = "cancelled"
                    await set_state(State.CANCELLING)

        state_lock.release()

def run_asyncio():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    start_server = websockets.serve(init, "0.0.0.0", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('--testing', action='store_true', default=False,
                   help='To run webserver without drinkmaker attached')
    parser.add_argument('--local', action='store_true', default=False,
                   help='To run webserver without drinkmaker attached')
    args = parser.parse_args()

    if not args.testing:
        setup_pigpio()

    http_thread = threading.Thread(target=http_server, args=[args.testing], daemon=True)
    http_thread.start()

    run_asyncio()


if __name__ == "__main__":
    main()
