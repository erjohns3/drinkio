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

pi.set_PWM_frequency(BUZZ_PIN, 800)
time.sleep(0.2)
pi.set_PWM_frequency(BUZZ_PIN, 1000)
time.sleep(0.2)
pi.set_PWM_frequency(BUZZ_PIN, 500)
time.sleep(0.2)
pi.set_PWM_frequency(BUZZ_PIN, 800)
time.sleep(0.2)
pi.set_PWM_frequency(BUZZ_PIN, 400)
time.sleep(0.5)

#################################################

# 100
# 160
# 200
# 250
# 320
# 400
# 500
# 800
# 1000
# 1600
# 2000
# 4000

stop()
