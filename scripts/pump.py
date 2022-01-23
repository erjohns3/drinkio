import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

PUMP_PIN = 17
pump_freq_normal = 5
steps = int(sys.argv[1])

duration = steps / pump_freq

pi.set_PWM_frequency(pump, pump_freq)

pi.set_PWM_dutycycle(PUMP_PIN, 50)

print(duration)
time.sleep(duration)

pi.set_PWM_dutycycle(pump, 0)