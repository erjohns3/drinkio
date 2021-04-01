import threading
import subprocess
#import RPi.GPIO as GPIO
import time
import datetime
import os
import sys
import json

#################################### gpio signals

def onRise(channel):
    print("rise: ", time.time())
    sys.stdout.flush()

#GPIO.setmode(GPIO.BOARD)
#GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
#GPIO.add_event_detect(11, GPIO.RISING, callback=onRise, bouncetime=200)
#GPIO.add_event_detect(11, GPIO.FALLING, callback=onFall, bouncetime=200)

#################################### text to speech

single = 0.6
pump_pin = 21

info = {
    "vodka": {
        "abv": 0.4
    }
}

pins = [25, 8, 7, 1, 12, 16, 20]

valves = {
    "vodka": 0,
    "rum": 1,
    "whiskey": 2,
    "tequila": 3,
    "fireball": 4,
    "orange juice": 5,
    "coke": 6,
    "ginger beer": 7,
    "club soda": 8,
    "lime": 9,
    "lemon": 10
}

drinks = {
    "Screwdriver": {
        "vodka": 1.5,
        "orange juice": 3
    },
    "Margarita": {
        
    }

}


while True:
    drink = input("Enter drink: ")

    if drink in drinks:
        for ingredient in drinks[drink]:
            if ingredient in valves:
                print("{}, {}, {}".format(ingredient, valves[ingredient], pins[valves[ingredient]]))

    #GPIO.output(12, GPIO.HIGH)

