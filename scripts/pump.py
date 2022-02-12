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

def check_cancel():
    global cancel_pour
    print("check cancel")

    cancel_lock.acquire()
    if cancel_pour:
        pass
    cancel_lock.release()
    return False

cancel_lock = threading.Lock()
cancel_pour = False

tick_prev = 0
tick_change = 0
flow_static = True

def flow_change(pin, level, tick):
    global flowing
    global flow_prev
    global tick_prev
    global tick_change
    global flow_static

    if flow_static:
        flow_static = False
        tick_change = tick

    if level == 2:
        flow_static = True

    print("flow: {}  -  {:.0f}  -  {:.0f}".format(level, (tick - tick_prev)/1000000, (tick - tick_change)/1000000))
    tick_prev = tick
    tmp = flowing

    if level == 1:
        flowing = True
        flow_prev = True
    elif level == 0:
        flow_prev = False
    elif flow_prev == False:
        flowing = False
        tick_change = tick

    #if tmp is not flowing:
        #print("flow: " + str(flowing) + ", " + str(tick/1000000))
    

FLOW_PIN = 17
COND_PIN = 23
ENABLE_PIN = 22
PUMP_PIN = 27
pump_freq = 320
steps = 0

pi.set_mode(FLOW_PIN, pigpio.INPUT)
pi.set_pull_up_down(FLOW_PIN, pigpio.PUD_OFF)
pi.callback(FLOW_PIN, pigpio.EITHER_EDGE, flow_change)
pi.set_watchdog(FLOW_PIN, 8000)

flowing = pi.read(FLOW_PIN) == 1
flow_prev = flowing
print("flow: " + str(flowing))

pi.set_mode(COND_PIN, pigpio.INPUT)
pi.set_pull_up_down(COND_PIN, pigpio.PUD_UP)

pi.set_mode(ENABLE_PIN, pigpio.OUTPUT)
pi.write(ENABLE_PIN, 0)
time.sleep(1)

pi.set_PWM_frequency(PUMP_PIN, pump_freq)
pump_freq = pi.get_PWM_frequency(PUMP_PIN)
duration = steps / pump_freq

print("freq: " + str(pump_freq))
print("time: " + str(duration))

pi.set_PWM_dutycycle(PUMP_PIN, 50)

# time.sleep(int(sys.argv[2]))

tick = 0
while True:
    #print("conductive: " + str(pi.read(FLOW_PIN)) + ",    tick: " + str(tick))
    tick+=1
    time.sleep(0.25)

stop()
