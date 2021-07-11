import asyncio
import websockets
import http.server
import socketserver
import threading
import json
import pathlib
import time
from enum import Enum

class State(Enum):
    STANDBY = 1
    READY = 2
    POURING = 3
    CANCELLING = 4
    CLEANING = 5

loc = pathlib.Path(__file__).parent.absolute()
f = open(str(loc)+"/config.json", "r")
config = f.read()
f.close()

socket_lock = threading.Lock()
user_queue = []
user_drink_name = {}
user_drink_ingredients = {}

status = {
    "position": -1,
    "users": 0,
    "drink": "",
    "timer": -1,
    "progress": -1
}

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

def http_server():
    httpd = socketserver.TCPServer(("", PORT), Handler)
    print("serving at port", PORT)
    httpd.serve_forever()

http_thread = threading.Thread(target=http_server, args=(), daemon=True)
http_thread.start()

#################################################
        
state = State.STANDBY
ready_wait = 30
ready_timer = False
ready_time = 0
progress = 30


def ready_start():
    global ready_timer
    global ready_time

    ready_timer = threading.Timer(ready_wait, ready_end)
    ready_timer.start()
    ready_time = time.time()


def ready_end():
    socket_lock.acquire()
    ready_reset()
    socket_lock.release()

def ready_reset():
    global state
    global user_queue

    user_queue.pop()
    if len(user_queue) == 0:
        state = State.STANDBY
    else:
        ready_start()

async def send_status(websocket):
    global state
    global user_queue
    global ready_time
    global status

    i = 1
    found = False
    for user in user_queue:
        if user == websocket.remote_address[0]:
            found = True
            break
        i = i+1
    if found:
        status["position"] = i
        status["drink"] = user_drink_name[user]
        if state == State.READY and user_queue[0] == websocket.remote_address[0]:
            status["timer"] = max(0, ready_time + ready_wait - time.time())
            status["progress"] = False
        elif state == State.POURING and user_queue[0] == websocket.remote_address[0]:
            status["timer"] = False
            status["progress"] = progress
        else:
            status["timer"] = False
            status["progress"] = False
    else:
        status["position"] = False
        status["drink"] = False
        status["timer"] = False
        status["progress"] = False
    status["users"] = len(user_queue)
    await websocket.send('{"status":' +json.dumps(status) + '}')

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer

    print("socket start: " + websocket.remote_address[0])
    await websocket.send(config)
    while True:
        msg_string = await websocket.recv()
        msg = json.loads(msg_string)
        print(msg)
        socket_lock.acquire()
        if 'type' in msg:
            if msg['type'] == "query":
                await send_status(websocket)

            elif msg['type'] == "queue" and 'name' in msg:
                if state == State.STANDBY:
                    ready_start()
                    state = State.READY
                
                add_user = True
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        add_user = False
                        break
                if add_user:
                    user_queue.append(websocket.remote_address[0])
                    
                user_drink_name[websocket.remote_address[0]] = msg['name']
                user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                await send_status(websocket)
            
            elif msg['type'] == "remove":
                if user_queue[0] != websocket.remote_address[0]:
                    user_queue.remove(websocket.remote_address[0])
                elif state == State.READY:
                    ready_timer.cancel()
                    ready_reset()
                    
                await send_status(websocket)

            elif msg['type'] == "pour":
                print("pour start")
                if state == State.READY and user_queue[0] == websocket.remote_address[0]:
                    ready_timer.cancel()
                    state = State.POURING
                    print("pour end 1")
                elif state == State.STANDBY and 'drink' in msg:
                    user_queue.append(websocket.remote_address[0])
                    user_drink_name[websocket.remote_address[0]] = msg['name']
                    user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                    state = State.POURING
                    print("pour end 2")
                print("pour end")
                await send_status(websocket)
                

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == websocket.remote_address[0]:
                    state = State.CANCELLING
                    await send_status(websocket)

        socket_lock.release()

start_server = websockets.serve(init, "192.168.86.47", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

#################################################
