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

TILT_UP = 400000
TILT_DOWN = 500000
TILT_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

####################################

if sys.argv[1] == "down":
    tilt_curr = TILT_UP
    print("tilt down")
    while tilt_curr != TILT_DOWN:
        tilt_curr = min(tilt_curr + (TILT_SPEED * TILT_PERIOD), TILT_DOWN)
        pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
        await asyncio.sleep(TILT_PERIOD)
else:
    tilt_curr = TILT_DOWN
    print("tilt down")
    while tilt_curr != TILT_UP:
        tilt_curr = max(tilt_curr + (TILT_SPEED * TILT_PERIOD), TILT_UP)
        pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
        await asyncio.sleep(TILT_PERIOD)
