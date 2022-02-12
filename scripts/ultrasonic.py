import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

def stop():
    pi.stop()

def signal_handler(sig, frame):
    print('Ctrl+C')
    stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

TRIGGER_PIN = 23
ECHO_PIN = 24

trigger_start = 0

def echo(pin, level, tick):
    global trigger_start
    if level == 1:
        trigger_start = tick
    elif level == 0:
        distance = pigpio.tickDiff(trigger_start, tick)
        if distance > 50 and distance < 1200:
            print("TRUE - {}".format(distance))
        else:
            print("     - {}".format(distance))

pi.set_mode(ECHO_PIN, pigpio.INPUT)
pi.set_pull_up_down(ECHO_PIN, pigpio.PUD_OFF)
pi.callback(ECHO_PIN, pigpio.EITHER_EDGE, echo)

pi.set_mode(TRIGGER_PIN, pigpio.OUTPUT)
pi.write(TRIGGER_PIN, 0)

while True:
    start = time.time()
    #pi.write(TRIGGER_PIN, 1)
    #time.sleep(0.00001)
    #pi.write(TRIGGER_PIN, 0)
    pi.gpio_trigger(TRIGGER_PIN, 10, 1)
    diff = time.time() - start
    #print(diff * 1000000)
    time.sleep(1)

stop()
