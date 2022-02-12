import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

def stop():
    pi.set_PWM_dutycycle(BUZZ_PIN, 0)
    pi.stop()

def signal_handler(sig, frame):
    print('Ctrl+C')
    stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
    
BUZZ_PIN = 5

pi.set_mode(BUZZ_PIN, pigpio.OUTPUT)
pi.set_PWM_dutycycle(BUZZ_PIN, 50)

#################################################

pi.set_PWM_frequency(BUZZ_PIN, 500)
print(str(pi.get_PWM_frequency(BUZZ_PIN)))
time.sleep(0.25)

pi.set_PWM_frequency(BUZZ_PIN, 750)
print(str(pi.get_PWM_frequency(BUZZ_PIN)))
time.sleep(0.25)

pi.set_PWM_frequency(BUZZ_PIN, 1000)
print(str(pi.get_PWM_frequency(BUZZ_PIN)))
time.sleep(0.25)

#################################################

stop()
