import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

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

####################################

pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
time.sleep(2)

pan_curr = ports[int(sys.argv[1])]
pan_goal = ports[int(sys.argv[2])]

while pan_curr != pan_goal:
    if pan_goal > pan_curr:
        pan_curr = min(pan_curr + (PAN_SPEED * PAN_PERIOD), pan_goal)
    else:
        pan_curr = max(pan_curr - (PAN_SPEED * PAN_PERIOD), pan_goal)
    pi.hardware_PWM(PAN_PIN, 333, int(pan_curr))
    time.sleep(PAN_PERIOD)
