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
    STANDBY = 1
    READY = 2
    POURING = 3
    CANCELLING = 4
    CLEANING = 5

clear_time = {
    "basement": 8
    "hottub": 18
}

class User:
    def __init__(self, uuid):
        print("new user")
        self.uuid = uuid
        self.name = ""
        self.weight = 0 # pounds
        self.sex = ""
        self.drinks = [] # shots
        self.alcohol_prev = 0 # grams
    
    def add_drink(self, amount):
        self.drinks.append({'amount': amount, 'time': time.time()})
        print("add drink")

    def get_drinks(self):
        sum = 0
        while len(self.drinks) > 0 and self.drinks[0]['time'] < time.time() - 43200:
            self.drinks.pop(0)
        for drink in self.drinks:
            sum += drink['amount']
        return sum

    def get_bac(self):
        # bac = (1 mg of alcohol) / (100 ml of blood)
        if len(self.drinks) > 0 and self.weight > 0:
            if self.sex == "male":
                blood = self.weight * 0.453592 * 75
            elif self.sex == "female":
                blood = self.weight * 0.453592 * 65
            else:
                return 0

            #alcohol_mult = 17.74 # ml of alcohol per drink
            alcohol_mult = 14 # grams of alcohol per drink
            alcohol = self.drinks[0]['amount'] * alcohol_mult

            for i in range(1, len(self.drinks)):
                alcohol -= (0.015 * (blood / 10) * ((self.drinks[i]['time']-self.drinks[i-1]['time'])/3600))
                if alcohol < 0:
                    alcohol = 0
                alcohol += self.drinks[i]['amount'] * alcohol_mult
                
            alcohol -= (0.015 * (blood / 10) * ((time.time()-self.drinks[len(self.drinks)-1]['time'])/3600))

            if alcohol < 0:
                alcohol = 0

            bac = alcohol / (blood / 10)
            return bac
        else:
            return 0

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
user_queue = []
user_drink_name = {}
user_drink_ingredients = {}
users = {}
song = vlc.MediaPlayer()
video_once = vlc.MediaPlayer()
video_loop = False
args = False

status = {
    "position": False,
    "users": 0,
    "drink": False,
    "timer": False,
    "progress": False
}

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
TILT_DOWN = 480000
TILT_DOWN_SPEED = 50000 # pwm change per second
TILT_UP_SPEED = 500000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 150000 # pwm change per second
PAN_PERIOD = 0.01

pan_curr = 495000
tilt_curr = TILT_UP

pi = None

TRIGGER_PIN = 23
ECHO_PIN = 24

trigger_start = 0
cup = True

def echo(pin, level, tick):
    global trigger_start
    global cup
    if level == 1:
        trigger_start = tick
    elif level == 0:
        distance = pigpio.tickDiff(trigger_start, tick)
        if distance > 50 and distance < 1200:
            cup = True

##########################################

RED_PIN = 9
GREEN_PIN = 10
BLUE_PIN = 11

async def light_making():
    tick = 0
    while True:
        val = int(tick if (tick <= 100) else (200 - tick))
        pi.set_PWM_dutycycle(GREEN_PIN, (0.5*val + 50)*0.2)
        pi.set_PWM_dutycycle(BLUE_PIN, (0.5*val + 50))
        tick = (tick + 25) % 200
        await asyncio.sleep(0.02604)

async def light_cleaning():
    val = 0
    while True:
        pi.set_PWM_dutycycle(RED_PIN, val)
        val = 100 - val
        await asyncio.sleep(0.15)

async def light_finished():
    tick = 100
    while True:
        val = int(tick if (tick <= 100) else (200 - tick))
        pi.set_PWM_dutycycle(GREEN_PIN, val)
        tick = (tick + 20) % 200
        await asyncio.sleep(0.05)

async def light_reset():
    pi.set_PWM_dutycycle(RED_PIN, 0)
    pi.set_PWM_dutycycle(GREEN_PIN, 0)
    pi.set_PWM_dutycycle(BLUE_PIN, 0)

######################################

BUZZ_PIN = 5

async def buzzer_making():
    pi.set_PWM_dutycycle(BUZZ_PIN, 50)

    pi.set_PWM_frequency(BUZZ_PIN, 500)
    await asyncio.sleep(0.25)
    pi.set_PWM_frequency(BUZZ_PIN, 750)
    await asyncio.sleep(0.25)
    pi.set_PWM_frequency(BUZZ_PIN, 1000)
    await asyncio.sleep(0.25)

    pi.set_PWM_dutycycle(BUZZ_PIN, 0)

async def buzzer_finished():
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

async def buzzer_cleaning():
    pi.set_PWM_dutycycle(BUZZ_PIN, 50)

    pi.set_PWM_frequency(BUZZ_PIN, 1000)
    await asyncio.sleep(0.25)
    pi.set_PWM_frequency(BUZZ_PIN, 750)
    await asyncio.sleep(0.25)
    pi.set_PWM_frequency(BUZZ_PIN, 500)
    await asyncio.sleep(0.25)

    pi.set_PWM_dutycycle(BUZZ_PIN, 0)

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


with open(path.join(drink_io_folder, 'rasp_pi_port_config.json'), 'r') as f:
    rasp_pi_port_config = json.loads(f.read())

ports = rasp_pi_port_config['ports']


with open(path.join(drink_io_folder, 'songs.json'), 'rb') as f:
    drink_songs = json.loads(f.read().decode("UTF-8"))

with open(path.join(drink_io_folder, 'admins.json'), 'rb') as f:
    admins = json.loads(f.read().decode("UTF-8"))

# helper functions

# ASSUMES HAS ALREADY BEEN LOCKED
def dump_ingredients_owned_to_file():
    print("----dump ingredients to to file start----", flush=True)
    with open(path.join(drink_io_folder, 'ingredients_owned.json'), 'w') as f:
        new_dict_to_dump = {}
        # for k, v in ingredients.values():
        for k in sorted(list(ingredients.keys()), key = lambda x: ingredients[x]['port']):
            v = ingredients[k]
            new_dict_to_dump[k] = v.copy()
        
        json.dump(new_dict_to_dump, f, indent=2)
        print("----dump ingredients to to file done----", flush=True)
    

to_send_to_client = {}

# prepping data from the "abs_of_ingredients.json", "recipes.json" and "ingredients_owned.json"

def load_config_from_files(lock):
    lock.acquire()
    global to_send_to_client
    global drinks
    global ingredients

    with open(path.join(drink_io_folder, 'ingredients_owned.json'), 'r') as f:
        owned_ingredients = json.loads(f.read())
    with open(path.join(drink_io_folder, 'recipes.json'), 'rb') as f:
        drink_recipes = json.loads(f.read().decode("UTF-8"))

    # removes recipes we dont have from drinks
    # to_remove = set()
    # drinks_with_owned_ingredients = {}
    # for key, value in drink_recipes.items():
    #     drinks_with_owned_ingredients[key] = {}
    #     for ingredient in value['ingredients']:
    #         if 'ingredient' in ingredient and ingredient['ingredient'] not in owned_ingredients:
    #             to_remove.add(key)
    #             continue
    #         if 'amount' in ingredient:
    #             drinks_with_owned_ingredients[key][ingredient['ingredient']] = ingredient['amount']

    # for i in to_remove:
    #     del drinks_with_owned_ingredients[i]

    to_send_to_client['drinks'] = drink_recipes
    to_send_to_client['ingredients'] = owned_ingredients
    drinks = drink_recipes
    ingredients = owned_ingredients
    lock.release()


load_config_from_files(config_lock)
#dump_ingredients_owned_to_file()

# watchdog for "ingredients_owned.json" list
class MyWatchdogMonitor(FileSystemEventHandler):
    def __init__(self, _config_lock, f_load_config_from_files):
        self.file_to_watch = 'ingredients_owned.json'
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

####################################

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

    ingredient_count = 0
    ingredient_index = 0
    for ingredient in drink:
        if drink[ingredient] > 0:
            ingredient_count += 1

    if outlet == 'basement':
        pi.write(VALVE_PIN, 1)
    elif outlet == 'hottub':
        pi.write(VALVE_PIN, 0)

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
            progress = (ingredient_index + 0.5) / ingredient_count * 100
            await broadcast_status()
        state_lock.release()

        pi.set_PWM_dutycycle(PUMP_PIN, 0)

        flow_time = (drink[ingredient] - 0.121) / 0.256
        print("pump time: {} - {}".format(drink[ingredient], flow_time), flush=True)

        print("tilt down", flush=True)
        while tilt_curr != TILT_DOWN:
            if await check_cancel(): return
            tilt_curr = min(tilt_curr + (TILT_DOWN_SPEED * TILT_PERIOD), TILT_DOWN)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)

        pi.set_PWM_dutycycle(PUMP_PIN, 50)
        flow_start = False
        elapsed = 0

        while True:
            if await check_cancel(): return

            flow = pi.read(FLOW_PIN) == 1

            if flow and not flow_start:
                flow_start = time.time()
                print("flowing: " + str(elapsed))

            if flow_start and time.time() >= flow_start + flow_time:
                break
            
            if (elapsed > FLOW_TIMEOUT and not flow_start) or (not flow and flow_start):
                print("ingredient empty")
                config_lock.acquire()
                ingredients[ingredient]["empty"] = True
                dump_ingredients_owned_to_file()
                config_lock.release()
                state_lock.acquire()
                await broadcast_config()
                state_lock.release()
                break

            elapsed = elapsed + FLOW_PERIOD
            await asyncio.sleep(FLOW_PERIOD)

        while tilt_curr != TILT_UP:
            tilt_curr = max(tilt_curr - (TILT_UP_SPEED * TILT_PERIOD), TILT_UP)
            pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
            await asyncio.sleep(TILT_PERIOD)

        print("tilt up done", flush=True)

        state_lock.acquire()
        if state == State.POURING:
            progress = (ingredient_index + 1.0) / ingredient_count * 100
            await broadcast_status()
        state_lock.release()

        ingredient_index = ingredient_index + 1

    await asyncio.sleep(clear_time[outlet])
    pi.set_PWM_dutycycle(PUMP_PIN, 0)
    pi.write(ENABLE_PIN, 1)

async def pour_cycle(drink, name, outlet):
    global state
    global cancel_pour
    global song
    global video_once
    global cup

    #################################
    song.stop()
    print(drink_songs, flush=True)
    print(name, flush=True)
    video_once.stop()
    video_once = vlc.MediaPlayer("video/make.mp4")
    video_once.play()
    if name in drink_songs:
        song = vlc.MediaPlayer("songs/"+drink_songs[name]+".mp4")
        print("playing custom", flush=True)
    else:
        song = vlc.MediaPlayer("songs/luigi.mp4")
        print("playing default", flush=True)
    song.play()
    ##############################

    light_task = asyncio.create_task(light_making())
    asyncio.create_task(buzzer_making())

    print("pour drink:", flush=True)
    print(drink, flush=True)
    await pour_drink(drink, outlet)
    print("drink done", flush=True)
    song.stop()

    light_task.cancel()
    await light_reset()

    ###############################

    video_once.stop()
    video_once = vlc.MediaPlayer("video/serve.mp4")
    video_once.play()

    light_task = asyncio.create_task(light_finished())
    asyncio.create_task(buzzer_finished())

    cup = True
    while cup:
        pi.gpio_trigger(TRIGGER_PIN, 10, 1)
        await asyncio.sleep(0.5)

    light_task.cancel()
    await light_reset()

    video_once.stop()
    video_once = vlc.MediaPlayer("video/clean.mp4")
    video_once.play()

    light_task = asyncio.create_task(light_cleaning())
    asyncio.create_task(buzzer_cleaning())

    state_lock.acquire()
    state = State.CLEANING
    print("----CLEANING----", flush=True)
    await broadcast_status()
    state_lock.release()

    cancel_lock.acquire()
    cancel_pour = False
    cancel_lock.release()

    print("pour clean:")
    print(clean, flush=True)
    await pour_drink(clean, outlet)
    print("clean done", flush=True)

    state_lock.acquire()
    await state_reset()
    state_lock.release()

    light_task.cancel()
    await light_reset()

    video_once.stop()
    video_once = vlc.MediaPlayer("video/done.mp4")
    video_once.play()

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

def http_server(testing=False):
    httpd = http.server.ThreadingHTTPServer(("", PORT), Handler)
    print("serving at port " + str(PORT), flush=True)
    httpd.serve_forever()


#################################################

state = State.STANDBY
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
    global state
    global user_queue

    user_queue.pop(0)
    if len(user_queue) == 0:
        state = State.STANDBY
        print("----STANDBY----", flush=True)
    else:
        state = State.READY
        print("----READY----", flush=True)
        await ready_start()
    await broadcast_status()

async def send_status(socket, uuid):
    global status

    i = 1
    found = False
    for user in user_queue:
        if user == uuid:
            found = True
            break
        i = i+1
    if found:
        status["position"] = i
        status["drink"] = user_drink_name[user]
        if state == State.READY and user_queue[0] == uuid:
            status["timer"] = max(0, ready_time + ready_wait - time.time())
            status["progress"] = False
        elif state == State.POURING and user_queue[0] == uuid:
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
    print(status, flush=True)
    try:
        message = {
            'status': status
        }
        await socket.send(json.dumps(message))
    except:
        print("socket send failed", flush=True)

async def broadcast_status():
    global connection_list
    
    i=0
    while i < len(connection_list):
        if connection_list[i]['user'] is not False:
            await send_status(connection_list[i]['socket'], connection_list[i]['user'].uuid)
            i=i+1


async def broadcast_config():
    global connection_list
    
    i=0
    while i < len(connection_list):
        config_lock.acquire()
        message = {
            'drinks': drinks,
            'ingredients': ingredients
        }
        dump = json.dumps(message)
        config_lock.release()
        await connection_list[i]['socket'].send(dump)
        i=i+1


async def send_user(socket, uuid):
    user = users[uuid]
    message = {
        'user': {
            'name': user.name,
            'weight': user.weight,
            'sex': user.sex,
            'drinks': user.get_drinks(),
            'bac': user.get_bac()
        }
    }
    await socket.send(json.dumps(message))

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer
    global cancel_pour
    global progress
    global ingredients
    global video_once
    global video_loop

    #video_once.stop()
    #video_once = vlc.MediaPlayer("video/hello.mp4")
    #video_once.play()

    state_lock.acquire()
    if len(connection_list) == 0:
        print("first user on")
        video_loop = OMXPlayer('video/idle.mp4', '--loop')
    connection_list.append({'socket': websocket, 'user': False})
    print("init: " + websocket.remote_address[0], flush=True)
    state_lock.release()
    
    config_lock.acquire()
    message = {
        'drinks': drinks,
        'ingredients': ingredients
    }
    dump = json.dumps(message)
    config_lock.release()
    await websocket.send(dump)
    while True:
        try:
            msg_string = await websocket.recv()
        except:
            print("socket recv failed", flush=True)
            state_lock.acquire()
            i=0
            while i < len(connection_list):
                if connection_list[i]['socket'] == websocket:
                    connection_list.pop(i)
                    #video_once.stop()
                    #video_once = vlc.MediaPlayer("video/bye.mp4")
                    #video_once.play()

                    if len(connection_list) == 0:
                        print("last user off")
                        video_loop.quit()
                    break
                i=i+1
            state_lock.release()
            break
        print("socket recv")
        msg = json.loads(msg_string)
        print(msg, flush=True)
        state_lock.acquire()
        if 'type' in msg:
            print("----local: " + str(args.local) + ", address: " + websocket.remote_address[0], flush=True)
            if msg['type'] == "query":
                for connection in connection_list:
                    if connection['socket'] == websocket:
                        if msg['uuid'] in users:
                            print("existing user")
                            await send_user(websocket, msg['uuid'])
                        else:
                            print("new user")
                            users[msg['uuid']] = User(msg['uuid'])
                        connection['user'] = users[msg['uuid']]
                await send_status(websocket, msg['uuid'])

            elif args.local and websocket.remote_address[0] != "192.168.86.1" and msg['uuid'] not in admins:
                print("non local", flush=True)

            elif msg['type'] == "user" and 'name' in msg and 'weight' in msg and 'sex' in msg:

                users[msg['uuid']].name = msg['name']
                users[msg['uuid']].weight = msg['weight']
                users[msg['uuid']].sex = msg['sex']
                await send_user(websocket, msg['uuid'])

            elif msg['type'] == "ingredient" and 'name' in msg and 'empty' in msg:
                if msg['uuid'] in admins:
                    print("admin: "+admins[msg['uuid']]+", "+msg['uuid'], flush=True)
                    config_lock.acquire()
                    ingredients[msg['name']]["empty"] = msg['empty']
                    dump_ingredients_owned_to_file()
                    config_lock.release()
                    await broadcast_config()                    

            elif msg['type'] == "queue" and 'name' in msg and 'ingredients' in msg:
                print("queue add", flush=True)
                
                add_user = True
                for user in user_queue:
                    if user == msg['uuid']:
                        add_user = False
                        break
                if add_user:
                    user_queue.append(msg['uuid'])
                    
                user_drink_name[msg['uuid']] = msg['name']
                user_drink_ingredients[msg['uuid']] = msg['ingredients']

                if state == State.STANDBY:
                    state = State.READY
                    print("----READY----", flush=True)
                    await ready_start()

                await broadcast_status()
            
            elif msg['type'] == "remove":
                found = False
                i = 0
                for user in user_queue:
                    if user == msg['uuid']:
                        found = True
                        break
                    i = i+1
                if found:
                    if i > 0:
                        user_queue.remove(msg['uuid'])
                        await broadcast_status()
                    elif state == State.READY:
                        ready_timer.cancel()
                        await state_reset()

            elif msg['type'] == "pour" and 'name' in msg and 'ingredients' in msg:
                if state == State.STANDBY:
                    full = True
                    alcohol = 0
                    config_lock.acquire()
                    for ingredient in msg['ingredients']:
                        alcohol += msg['ingredients'][ingredient] * ingredients[ingredient]['abv'] / 0.6
                        if ingredients[ingredient]["empty"]:
                            full = False
                    config_lock.release()
                    if full:
                        if 'uuid' in msg and 'name' in msg and 'ingredients' in msg:
                            tracking.DB.record_pour(msg['uuid'], msg['name'], msg['ingredients'])
                        user_queue.append(msg['uuid'])
                        user_drink_name[msg['uuid']] = msg['name']
                        user_drink_ingredients[msg['uuid']] = msg['ingredients']
                        state = State.POURING
                        print("----POURING----", flush=True)
                        asyncio.create_task(pour_cycle(user_drink_ingredients[user_queue[0]], user_drink_name[user_queue[0]], msg['outlet']))
                        progress = 1
                        await broadcast_status()
                        users[msg['uuid']].add_drink(alcohol)
                        await send_user(websocket, msg['uuid'])

            elif msg['type'] == "pour" :
                if state == State.READY and user_queue[0] == msg['uuid'] and user_queue[0] in user_drink_ingredients:
                    full = True
                    alcohol = 0
                    config_lock.acquire()
                    for ingredient in user_drink_ingredients[user_queue[0]]:
                        alcohol += user_drink_ingredients[user_queue[0]][ingredient] * ingredients[ingredient]['abv'] / 0.6
                        if ingredients[ingredient]["empty"]:
                            full = False
                    config_lock.release()
                    if full:
                        if 'uuid' in msg and 'name' in msg and 'ingredients' in msg:
                            tracking.DB.record_pour(msg['uuid'], msg['name'], msg['ingredients'])
                        ready_timer.cancel()
                        state = State.POURING
                        print("----POURING----", flush=True)
                        asyncio.create_task(pour_cycle(user_drink_ingredients[user_queue[0]], user_drink_name[user_queue[0]], msg['outlet']))
                        progress = 1
                        await broadcast_status()
                        users[msg['uuid']].add_drink(alcohol)
                        await send_user(websocket, msg['uuid'])

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == msg['uuid']:
                    state = State.CANCELLING
                    print("----CANCELLING----", flush=True)
                    print("pour cancel", flush=True)
                    cancel_lock.acquire()
                    cancel_pour = True
                    cancel_lock.release()
                    user_queue[0] = "cancelled"
                    await broadcast_status()

        state_lock.release()

def video_manager():
    while True:
        time.sleep(30)

def run_asyncio():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    #asyncio.create_task(video_manager())

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
