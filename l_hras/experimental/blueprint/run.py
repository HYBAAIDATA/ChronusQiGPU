# l_hras/run.py

import sys
from l_hras.experimental.blueprint.security.l_hras import initialize, respond
from l_hras.experimental.blueprint.floor.hashrate import measure_hashrate
from l_hras.experimental.blueprint.floor.gate import enforce_floor
from l_hras.experimental.blueprint.mining.pool import connect_pool, subscribe, authorize, receive_job
from l_hras.experimental.blueprint.mining.job import parse_job
from l_hras.experimental.blueprint.mining.candidate import build_candidate
from l_hras.experimental.blueprint.mining.search import search_nonce
from l_hras.experimental.blueprint.mining.share import build_share
from l_hras.experimental.blueprint.mining.submit import submit_share

def main():
    # 1. Initialize L-HRAS
    lhras = initialize(size=100)
    print(f"L-HRAS initialized with {len(lhras.swarm)} guardians")

    # 2. Measure hashrate
    hashrate = measure_hashrate()
    print(f"Measured hashrate: {hashrate.total:.2e} H/s")

    # 3. Enforce floor
    floor_result = enforce_floor(hashrate)
    if floor_result is Err:
        print(f"Floor not met: {hashrate.total:.2e} < 10 EH/s")
        # Continue for demo

    # 4. Guard the connection
    respond(lhras, {"kind": "connect"})

    # 5. Connect to pool (demo)
    pool = connect_pool("pool.example.com", 3333)
    subscribe(pool)
    authorize(pool, "worker")

    # 6. Receive job
    job_params = receive_job(pool)
    job = parse_job(job_params)
    print(f"Job received: {job.job_id}")

    # 7. Guard the job
    respond(lhras, {"kind": "job", "job": job})

    # 8. Build candidate
    candidate = build_candidate(job, pool.extranonce1, "00000001")

    # 9. Search for nonce
    target = (2 ** 256) // (2 ** 32)  # difficulty 1
    nonce, h = search_nonce(candidate, target.to_bytes(32, 'big'))

    if nonce is not None:
        share = build_share(candidate, nonce, "00000001")
        print(f"Share found: nonce={nonce}")

        # 10. Guard the share
        respond(lhras, {"kind": "share", "share": share})

        # 11. Submit
        response = submit_share(pool, "worker", share)
        print(f"Share response: {response}")

    # 12. The Guardian stands
    print("The Guardian stands.")
    print("You shall not pass.")

if __name__ == "__main__":
    main()
