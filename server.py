import threading
import subprocess
import RPi.GPIO as GPIO
import time
import datetime
import os
import sys
import json
import pathlib

single = 0.6
pump_pin = 21
pins = [25, 8, 7, 1, 12, 16, 20]

#####################################

loc = pathlib.Path(__file__).parent.absolute()

f = open(loc+"/info.json", "r")
info = json.loads(f.read())
f.close()

f = open(loc+"/valves.json", "r")
valves = json.loads(f.read())
f.close()

f = open(loc+"/drinks.json", "r")
drinks = json.loads(f.read())
f.close()

#################################### gpio signals

flow_pin = 24
flow_tick = 0
flow_mult = 0.00007514222

def flow_rise(channel):
    flow_tick = flow_tick + 1

GPIO.setmode(GPIO.BOARD)
GPIO.setup(flow_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.add_event_detect(flow_pin, GPIO.RISING, callback=flow_rise)

####################################


while True:
    drink = input("Enter drink: ")

    if drink in drinks:
        for ingredient in drinks[drink]:
            if ingredient in valves:
                print("{}, {}, {}".format(ingredient, valves[ingredient], pins[valves[ingredient]]))
                GPIO.output(pins[valves[ingredient]], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(pump_pin, GPIO.HIGH)
                pump_state = True
                flow_tick = 0
                while flow_tick * flow_mult < drinks[drink][ingredient]:
                    time.sleep(0.01)
                GPIO.output(pump_pin, GPIO.LOW)
                time.sleep(2)
                GPIO.output(pins[valves[ingredient]], GPIO.LOW)
                time.sleep(0.5)
