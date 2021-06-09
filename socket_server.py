import asyncio
import websockets
import http.server
import socketserver
import threading
import json


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

async def hello(websocket, path):
    #name = await websocket.recv()
    msg = "hello"
    await websocket.send(msg)
    print("spcket init")

start_server = websockets.serve(hello, "127.0.0.1", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

#################################################