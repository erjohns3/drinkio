import threading
import pigpio
import time
import sys
import json
import signal
import pathlib

pi = pigpio.pi()

PAN_PIN = 12
TILT_PIN = 13
PUMP_PIN = 27
FLOW_PIN = 17

FLOW_PERIOD = 0.01
FLOW_TIMEOUT = 5

TILT_UP = 400000
TILT_DOWN = 485000
TILT_DOWN_SPEED = 50000 # pwm change per second
TILT_UP_SPEED = 500000 # pwm change per second
TILT_PERIOD = 0.01

port = int(sys.argv[1])
flow_goal = float(sys.argv[2])

def signal_handler(sig, frame):
    print('Ctrl+C', flush=True)
    pi.write(PUMP_PIN, 1)
    pi.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#####################################

f = open('rasp_pi_port_config.json', "r")
ports = json.loads(f.read())['ports']
f.close()


#####################################

pi.set_mode(PUMP_PIN, pigpio.OUTPUT)
pi.write(PUMP_PIN, 1)

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

####################################

print("Drink: {}, Angle: {}, Amount: {}".format(port, ports[port], flow_goal), flush=True)

pi.hardware_PWM(TILT_PIN, 333, TILT_UP)
time.sleep(2)
pi.hardware_PWM(PAN_PIN, 333, ports[port])
time.sleep(2)
pi.write(PUMP_PIN, 0)

elapsed = 0
flow_prev = 0

tilt_curr = TILT_UP
while tilt_curr != TILT_DOWN:
    tilt_curr = min(tilt_curr + (TILT_DOWN_SPEED * TILT_PERIOD), TILT_DOWN)
    pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
    time.sleep(TILT_PERIOD)

while True:
    flow_lock.acquire()
    if flow_tick >= flow_goal:
        print("----done", flush=True)
        break
    
    if elapsed > 8:
        if flow_tick - flow_prev <= 3:
            print("----empty", flush=True)
            break
        flow_prev = flow_tick
        elapsed = 4

    elapsed = elapsed + FLOW_PERIOD
    flow_lock.release()
    time.sleep(FLOW_PERIOD)

flow_lock.release()

tilt_curr = TILT_DOWN
print("tilt up")
while tilt_curr != TILT_UP:
    tilt_curr = max(tilt_curr - (TILT_UP_SPEED * TILT_PERIOD), TILT_UP)
    pi.hardware_PWM(TILT_PIN, 333, int(tilt_curr))
    time.sleep(TILT_PERIOD)
time.sleep(7)

pi.write(PUMP_PIN, 1)
