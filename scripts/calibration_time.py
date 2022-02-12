import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

def stop():
    pi.set_PWM_dutycycle(PUMP_PIN, 0)
    pi.write(ENABLE_PIN, 1)
    pi.stop()

def signal_handler(sig, frame):
    print('Ctrl+C')
    stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

cancel_lock = threading.Lock()
cancel_pour = False

FLOW_PERIOD = 0.005
FLOW_TIMEOUT = 15

TILT_UP = 400000
TILT_DOWN = 485000
TILT_DOWN_SPEED = 50000 # pwm change per second
TILT_UP_SPEED = 50000 # pwm change per second
TILT_PERIOD = 0.01

PAN_SPEED = 150000 # pwm change per second
PAN_PERIOD = 0.01

PAN_PIN = 12
TILT_PIN = 13

FLOW_PIN = 17
COND_PIN = 23
ENABLE_PIN = 22
PUMP_PIN = 27

pan_curr = 495000
tilt_curr = TILT_UP

PUMP_FREQ = 320
PUMP_CAL = 1043.17710018 / PUMP_FREQ
volume = int(sys.argv[1])

pi.set_mode(FLOW_PIN, pigpio.INPUT)
pi.set_pull_up_down(FLOW_PIN, pigpio.PUD_OFF)

flow_time = (volume - 0.121) / 0.256
print("pump time: {} - {}".format(volume, flow_time), flush=True)

pi.set_mode(ENABLE_PIN, pigpio.OUTPUT)
pi.write(ENABLE_PIN, 0)

pi.set_PWM_frequency(PUMP_PIN, PUMP_FREQ)
pi.set_PWM_dutycycle(PUMP_PIN, 0)

print("tilt down", flush=True)
while tilt_curr != TILT_DOWN:
    tilt_curr = min(tilt_curr + (TILT_DOWN_SPEED * TILT_PERIOD), TILT_DOWN)
    pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
    time.sleep(TILT_PERIOD)

pi.set_PWM_dutycycle(PUMP_PIN, 50)
flow_start = False
elapsed = 0

while True:

    flow = pi.read(FLOW_PIN) == 1

    curr = time.time()

    if flow and not flow_start:
        flow_start = time.time()
        print("flowing: " + str(elapsed))

    if flow_start:
        print("flow {}".format(curr - flow_start))
    else:
        print("flow {}".format(flow))

    if flow_start and curr >= flow_start + flow_time:
        break
    
    if (elapsed > FLOW_TIMEOUT and not flow_start) or (not flow and flow_start):
        print("ingredient empty")
        break

    elapsed = elapsed + FLOW_PERIOD
    time.sleep(FLOW_PERIOD)

pi.set_PWM_dutycycle(PUMP_PIN, 0)
print("ingredient done", flush=True)

while tilt_curr != TILT_UP:
    tilt_curr = max(tilt_curr - (TILT_UP_SPEED * TILT_PERIOD), TILT_UP)
    pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
    time.sleep(TILT_PERIOD)

print("tilt up done", flush=True)

pi.set_PWM_dutycycle(PUMP_PIN, 50)
time.sleep(12)

stop()
