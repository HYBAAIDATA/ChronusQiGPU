# l_hras/mining/submit.py

import json
from l_hras.experimental.blueprint.mining.pool import PoolConnection
from l_hras.experimental.blueprint.mining.share import Share

def submit_share(pool: PoolConnection, worker: str, share: Share) -> dict:
    """Submit a share."""
    msg = {
        "id": 4,
        "method": "mining.submit",
        "params": [
            worker,
            share.job_id,
            share.extranonce2,
            share.ntime,
            format(share.nonce, '08x'),
        ],
    }
    pool.sock.sendall((json.dumps(msg) + "\n").encode())
    response = pool.sock.recv(4096)
    return json.loads(response.decode())
