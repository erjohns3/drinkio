import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

FLOW_PIN = 17

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

while True:
    time.sleep(0.1)
 
