import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

def stop():
    pi.write(VALVE_PIN, 1)
    pi.stop()

def signal_handler(sig, frame):
    print('Ctrl+C')
    stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
    
VALVE_PIN = 6

#################################################

pi.write(VALVE_PIN, 0)
time.sleep(7)

pi.write(VALVE_PIN, 1)
time.sleep(7)

#################################################

stop()
