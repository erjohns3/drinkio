import threading
import pigpio
import time
import sys
import json
import signal
import pathlib
from pynput.keyboard import Listener

pi = pigpio.pi()

PAN_PIN = 12
TILT_PIN = 13
PUMP_PIN = 27
FLOW_PIN = 17

FLOW_BIAS = 0.753
FLOW_MULT = 0.0374
FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 5

TILT_UP = 400000
TILT_DOWN = 500000
TILT_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 200000 # pwm change per second
PAN_PERIOD = 0.01

#####################################

loc = pathlib.Path(__file__).parent.absolute()
f = open(str(loc)+"/config.json", "r")
config = json.loads(f.read())
f.close()

drinks = config["drinks"]
ports = config["ports"]
ingredients = config["ingredients"]

####################################

pan_lock = threading.Lock()

pan_curr = int(sys.argv[1])
pan_goal = int(sys.argv[2])
if pan_curr <= 100:
    pan_curr = ports[pan_curr]
if pan_goal <= 100:
    pan_goal = ports[pan_goal]

print(pan_goal)

def on_press(key):
    if key == 'w':
        pan_lock.aquire()
        pan_goal = pan_goal + 1000
        print(pan_goal)
        pan_lock.release()
    if key == 's':
        pan_lock.aquire()
        pan_goal = pan_goal - 1000
        print(pan_goal)
        pan_lock.release()

with Listener(on_press=on_press, on_release=on_release) as listener:

while True:
    pan_lock.acquire()
    if pan_goal > pan_curr:
        pan_curr = min(pan_curr + (PAN_SPEED * PAN_PERIOD), pan_goal)
        pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
    elif pan_goal < pan_curr:
        pan_curr = max(pan_curr - (PAN_SPEED * PAN_PERIOD), pan_goal)
        pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
    pan_lock.release()
    time.sleep(PAN_PERIOD)
