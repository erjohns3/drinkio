import asyncio
import websockets
import http.server
import socketserver
import threading
import json
import pathlib

loc = pathlib.Path(__file__).parent.absolute()
f = open(str(loc)+"/config.json", "r")
config = f.read()
f.close()

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



#################################################

async def init(websocket, path):
    #name = await websocket.recv()
    await websocket.send(config)
    print("socket init")

start_server = websockets.serve(init, "192.168.86.42", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

#################################################