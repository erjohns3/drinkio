import threading
import subprocess
import pigpio
import time
import datetime
import os
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

PAN_PIN = 12
TILT_PIN = 13
PUMP_PIN = 27
FLOW_PIN = 17

FLOW_BIAS = 12
FLOW_MULT = 0.073
FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 5

TILT_UP = 450000
TILT_DOWN = 490000

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

while True:
    drink = input("Enter drink: ")

    if drink in drinks:
        #pi.write(PUMP_PIN, 0)

        for ingredient in drinks[drink]:
            print("Drink: {}, Angle: {}, Amount: {}".format(ingredient, ports[ingredients[ingredient]["port"]], drinks[drink][ingredient]), flush=True)
            pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
            time.sleep(4)
            pi.write(PUMP_PIN, 0)

            angle = ports[ingredients[ingredient]["port"]]
            if angle < 500000:
                pi.hardware_PWM(PAN_PIN, 333, 650000)
            else:
                pi.hardware_PWM(PAN_PIN, 333, 350000)
            time.sleep(2)

            pi.hardware_PWM(PAN_PIN, 333, angle)
            time.sleep(4)
            pi.hardware_PWM(TILT_PIN, 333, TILT_DOWN)
            time.sleep(2)

            flow_lock.acquire
            flow_tick = 0
            flow_lock.release

            elapsed = 0
            flow_prev = 0

            while True:
                flow_lock.acquire
                if (flow_tick + FLOW_BIAS) * FLOW_MULT > drinks[drink][ingredient]:
                    print("----done", flush=True)
                    break
                
                if elapsed > 5:
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
            pi.write(PUMP_PIN, 1)

        pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
        time.sleep(5)
        pi.write(PUMP_PIN, 1)
