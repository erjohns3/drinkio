import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

def stop():
    pi.set_PWM_dutycycle(RED_PIN, 0)
    pi.set_PWM_dutycycle(GREEN_PIN, 0)
    pi.set_PWM_dutycycle(BLUE_PIN, 0)
    pi.stop()

def signal_handler(sig, frame):
    print('Ctrl+C')
    stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
    
RED_PIN = 9
GREEN_PIN = 10
BLUE_PIN = 11

pi.set_mode(RED_PIN, pigpio.OUTPUT)
pi.set_mode(GREEN_PIN, pigpio.OUTPUT)
pi.set_mode(BLUE_PIN, pigpio.OUTPUT)

pi.set_PWM_frequency(RED_PIN, 1000)
pi.set_PWM_frequency(GREEN_PIN, 1000)
pi.set_PWM_frequency(BLUE_PIN, 1000)

tick = 100
speed = 25

red = [1, 0, 0]
orange = [1, 0.06, 0]
yellow = [1, 0.3, 0]
green = [0, 1, 0]
cyan = [0, 1, 0.4]
blue = [0, 0, 1]
magenta = [1, 0, 1]
pink = [1, 0, 0.2]

white = [1, 1, 1]

custom = [float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])]

color = custom

def pour():
    tick = 0
    color = [0, 0.2, 1]

    while True:

        val = int(tick if (tick <= 100) else (200 - tick))

        pi.set_PWM_dutycycle(GREEN_PIN, (0.5*val + 50)*0.2)
        pi.set_PWM_dutycycle(BLUE_PIN, (0.5*val + 50))
        
        tick = (tick + 25) % 200

        time.sleep(0.02604)

def clean():
    val = 0
    color = [1, 0, 0]

    while True:

        pi.set_PWM_dutycycle(RED_PIN, val)
        
        val = 100 - val

        time.sleep(0.15)

def done():
    tick = 100

    while True:

        val = int(tick if (tick <= 100) else (200 - tick))

        pi.set_PWM_dutycycle(GREEN_PIN, val)
        
        tick = (tick + 20) % 200

        time.sleep(0.05)

done()

stop()
