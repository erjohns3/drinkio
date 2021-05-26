import threading
import subprocess
import pigpio
import time
import datetime
import os
import sys
import json
import pathlib

pi = pigpio.pi()

single = 0.6

#####################################

pump_pin = 27

pi.set_mode(pump_pin, pigpio.OUTPUT)
pi.write(pump_pin, 1)

#####################################

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
FLOW_TIMEOUT = 5
flow_lock = threading.Lock()
flow_pin = 17
flow_tick = 0
flow_mult = 0.00007514222

def flow_rise(channel):
    global flow_tick
    flow_lock.acquire()
    flow_tick = flow_tick + 1
    flow_lock.release()

pi.set_mode(flow_pin, pigpio.INPUT)
pi.set_pull_up_down(flow_pin, pigpio.PUD_DOWN)
pi.callback(flow_pin, pigpio.RISING_EDGE, flow_rise)

####################################


while True:
    drink = input("Enter drink: ")

    if drink in drinks:
        for ingredient in drinks[drink]:
            print("{}, {}".format(ingredient, ports[ingredients[ingredient]["port"]]))
            pi.hardware_PWM(tilt_pin, 333, tilt_up)
            time.sleep(2)
            duty = ports[ingredients[ingredient]["port"]]
            
            if duty < 500000:
                pi.hardware_PWM(pan_pin, 333, 750000)
            else:
                pi.hardware_PWM(pan_pin, 333, 250000)

            time.sleep(1)
            pi.hardware_PWM(pan_pin, 333, duty)
            time.sleep(3)
            pi.hardware_PWM(tilt_pin, 333, tilt_down)
            time.sleep(2)
            
            pi.write(pump_pin, 0)

            flow_lock.acquire
            flow_tick = 0
            flow_lock.release

            elapsed = 0
            flow_prev = 0

            while True:
                flow_lock.acquire
                if flow_tick * flow_mult > drinks[drink][ingredient]:
                    break
                
                if elapsed > 5:
                    if flow_tick - flow_prev <= 3:
                        ingredients[ingredient]["empty"] = True
                        break
                    flow_prev = flow_tick
                    elapsed = 4

                elapsed = elapsed + FLOW_PERIOD
                flow_lock.release
                time.sleep(FLOW_PERIOD)

            flow_lock.release
            pi.hardware_PWM(tilt_pin, 333, tilt_up)
            time.sleep(1)

        time.sleep(4)
        pi.write(pump_pin, 1)
        time.sleep(2)
