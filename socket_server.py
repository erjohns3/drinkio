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

class AsyncTimer:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        self._task.cancel()

loc = pathlib.Path(__file__).parent.absolute()
f = open(str(loc)+"/config.json", "r")
config = json.loads(f.read())
f.close()

state_lock = threading.Lock()
socket_list = []
user_queue = []
user_drink_name = {}
user_drink_ingredients = {}

status = {
    "position": False,
    "users": 0,
    "drink": False,
    "timer": False,
    "progress": False,
    "tick": 0
}

#################################################

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

class ReuseAddrTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def http_server():
    httpd = ReuseAddrTCPServer(("", PORT), Handler)
    print("serving at port", PORT)
    httpd.serve_forever()

http_thread = threading.Thread(target=http_server, args=(), daemon=True)
http_thread.start()

#################################################
        
state = State.STANDBY
ready_wait = 20
ready_timer = False
ready_time = 0
progress = 30


async def ready_start():
    global ready_timer
    global ready_time

    ready_timer = AsyncTimer(ready_wait, ready_end)
    ready_time = time.time()


async def ready_end():
    state_lock.acquire()
    await state_reset()
    state_lock.release()

async def state_reset():
    global state
    global user_queue

    user_queue.pop(0)
    if len(user_queue) == 0:
        state = State.STANDBY
    else:
        await ready_start()
    await broadcast_status()

async def send_status(socket):
    global status

    i = 1
    found = False
    for user in user_queue:
        if user == socket.remote_address[0]:
            found = True
            break
        i = i+1
    if found:
        status["position"] = i
        status["drink"] = user_drink_name[user]
        if state == State.READY and user_queue[0] == socket.remote_address[0]:
            status["timer"] = max(0, ready_time + ready_wait - time.time())
            status["progress"] = False
        elif state == State.POURING and user_queue[0] == socket.remote_address[0]:
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
    status["tick"] = status["tick"] + 1
    status["users"] = len(user_queue)
    print(status)
    await socket.send('{"status":' +json.dumps(status) + '}')

async def broadcast_status():
    global socket_list
    
    i=0
    while i < len(socket_list):
        if socket_list[i].closed:
            socket_list.pop(i)
        else:
            await send_status(socket_list[i])
            i=i+1

#################################################

async def init(websocket, path):
    global state
    global user_queue
    global ready_timer

    state_lock.acquire()
    socket_list.append(websocket)
    print("add: " + websocket.remote_address[0])
    state_lock.release()

    await websocket.send(json.dumps(config))
    while True:
        msg_string = await websocket.recv()
        msg = json.loads(msg_string)
        print(msg)
        state_lock.acquire()
        if 'type' in msg:
            if msg['type'] == "query":
                await send_status(websocket)

            elif msg['type'] == "queue" and 'name' in msg and 'ingredients' in msg:
                print("queue add")
                if state == State.STANDBY:
                    await ready_start()
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
                await broadcast_status()
            
            elif msg['type'] == "remove":
                found = False
                i = 0
                for user in user_queue:
                    if user == websocket.remote_address[0]:
                        found = True
                        break
                    i = i+1
                if found:
                    if i > 0:
                        user_queue.remove(websocket.remote_address[0])
                        await broadcast_status()
                    elif state == State.READY:
                        ready_timer.cancel()
                        await state_reset()

            elif msg['type'] == "pour" and 'name' in msg and 'ingredients' in msg:
                if state == State.STANDBY:
                    user_queue.append(websocket.remote_address[0])
                    user_drink_name[websocket.remote_address[0]] = msg['name']
                    user_drink_ingredients[websocket.remote_address[0]] = msg['ingredients']
                    state = State.POURING
                    print("pour now")
                    await broadcast_status()

            elif msg['type'] == "pour" :
                if state == State.READY and user_queue[0] == websocket.remote_address[0]:
                    ready_timer.cancel()
                    state = State.POURING
                    print("pour queue")
                    await broadcast_status()

            elif msg['type'] == "cancel":
                if state == State.POURING and user_queue[0] == websocket.remote_address[0]:
                    state = State.CANCELLING
                    print("pour cancel")
                    await broadcast_status()

        state_lock.release()

start_server = websockets.serve(init, "0.0.0.0", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

#################################################
