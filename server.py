import threading
import subprocess
import RPi.GPIO as GPIO
import pigpio
import time
import datetime
import os
import sys
import json
import pathlib

pi = pigpio.pi()

single = 0.6

pump_pin = 27
pan_pin = 12
tilt_pin = 13

tilt_up = 450000
tilt_down = 485000

#####################################

loc = pathlib.Path(__file__).parent.absolute()
print(loc)
print(os.path.dirname(__file__))

f = open(str(loc)+"/config.json", "r")
config = json.loads(f.read())
f.close()

drinks = config["drinks"]
ports = config["ports"]
ingredients = config["ingredients"]

#################################### gpio signals

FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 8
flow_lock = threading.Lock()
flow_pin = 17
flow_tick = 0
flow_zero = 0
flow_mult = 0.00007514222

def flow_rise(channel):
    global flow_tick
    global flow_zero
    flow_lock.acquire()
    flow_tick = flow_tick + 1
    flow_zero = 0
    flow_lock.release()

GPIO.setmode(GPIO.BCM)
GPIO.setup(flow_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.add_event_detect(flow_pin, GPIO.RISING, callback=flow_rise)

####################################


while True:
    drink = input("Enter drink: ")

    if drink in drinks:
        for ingredient in drinks[drink]:
            print("{}, {}".format(ingredient, ports[ingredients[ingredient]["port"]]))
            pi.hardware_PWM(tilt_pin, 333, tilt_up)
            time.sleep(1)
            duty = ports[ingredients[ingredient]["port"]]
            if duty < 500000:
                pi.hardware_PWM(pan_pin, 333, 750000)
            else:
                pi.hardware_PWM(pan_pin, 333, 250000)
            time.sleep(1)
            pi.hardware_PWM(pan_pin, 333, duty)
            time.sleep(3)
            pi.hardware_PWM(tilt_pin, 333, tilt_down)
            time.sleep(1)
            
