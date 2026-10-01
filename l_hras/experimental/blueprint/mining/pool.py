# l_hras/mining/pool.py

import socket
import json
from dataclasses import dataclass

@dataclass
class PoolConnection:
    host: str
    port: int
    sock: socket.socket = None
    subscription_id: str = None
    extranonce1: str = None

def connect_pool(host: str, port: int) -> PoolConnection:
    """Connect to a Stratum pool."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return PoolConnection(host=host, port=port, sock=sock)

def subscribe(pool: PoolConnection) -> dict:
    """Send mining.subscribe."""
    msg = {"id": 1, "method": "mining.subscribe", "params": []}
    pool.sock.sendall((json.dumps(msg) + "\n").encode())
    response = pool.sock.recv(4096)
    data = json.loads(response.decode())
    pool.subscription_id = data.get("result", [None, None])[0]
    pool.extranonce1 = data.get("result", [None, None])[1]
    return data

def authorize(pool: PoolConnection, worker: str, password: str = "x") -> dict:
    """Send mining.authorize."""
    msg = {"id": 2, "method": "mining.authorize", "params": [worker, password]}
    pool.sock.sendall((json.dumps(msg) + "\n").encode())
    response = pool.sock.recv(4096)
    return json.loads(response.decode())

def receive_job(pool: PoolConnection) -> dict:
    """Receive mining.notify."""
    data = pool.sock.recv(4096)
    msg = json.loads(data.decode())
    if msg.get("method") == "mining.notify":
        return msg["params"]
    return None
