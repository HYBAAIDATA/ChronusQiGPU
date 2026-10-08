"""Voyage test orchestrator.

Spawns two real CIaaS HTTP server subprocesses against the same
feedback_state_path, drives the full intelligence voyage over HTTP, and
prints PASS/FAIL per assertion.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOOT = REPO / "tests" / "tmp_test_voyage" / "server_boot.py"
STATE = REPO / "tests" / "tmp_test_voyage" / "fb_state.json"
PORT = 8471
BASE = f"http://127.0.0.1:{PORT}"
TENANT = "voyage-tnt"

results = []


def report(name, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((name, passed))
    print(f"[{tag}] {name}" + (f" :: {detail}" if detail else ""), flush=True)


def req(method, path, body=None, tenant=TENANT, raw=None):
    """Returns (status, parsed_json_or_None, raw_text)."""
    headers = {}
    if tenant is not None:
        headers["X-CIAAS-Tenant"] = tenant
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            text = resp.read().decode()
            try:
                return resp.status, json.loads(text), text
            except json.JSONDecodeError:
                return resp.status, None, text
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text), text
        except json.JSONDecodeError:
            return e.code, None, text


def boot(state):
    env = dict(os.environ)
    # The box envrc puts a DIFFERENT checkout (repos/PYTHIPhiMiner) on
    # PYTHONPATH; pin PYTHONPATH to this repo so `toe` resolves locally.
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.Popen(
        [sys.executable, str(BOOT), "--port", str(PORT), "--state", str(state)],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    health = None
    lines = []
    deadline = time.time() + 120
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        lines.append(line.rstrip())
        if line.startswith("STARTUP_HEALTH "):
            health = json.loads(line[len("STARTUP_HEALTH "):])
        if line.strip() == "READY":
            return proc, health, lines
    return proc, health, lines


def kill(proc):
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=15)
        for l in out.splitlines():
            if l.strip():
                print("    server> " + l, flush=True)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    if STATE.exists():
        STATE.unlink()

    payload = {"payload": {"series": [0.1, 0.4, 0.2, 0.9, 0.5, 0.7, 0.3, 0.8]}}

    print("=" * 70)
    print("INSTANCE 1 — fresh state path")
    print("=" * 70)
    proc1, health1, lines1 = boot(STATE)
    if health1 is None:
        report("instance-1 boot", False, "no STARTUP_HEALTH; output: " + " | ".join(lines1[-5:]))
        kill(proc1)
        return 1
    report("instance-1 boot", True)

    # 1-2. predict/explain/forecast/causal -> 200 + decision_id
    ids = {}
    for op in ["predict", "explain", "forecast", "causal"]:
        st, body, _ = req("POST", f"/api/v1/ciaas/{op}", body=payload)
        did = (body or {}).get("decision_id")
        ok = st == 200 and (body or {}).get("ok") is True and isinstance(did, str) and did
        extra = ""
        if op == "predict" and body:
            extra = f"receipt={'receipt' in body}, state_tomography={'state_tomography' in (body.get('result') or {})}"
        report(f"instance-1 {op} 200+decision_id", ok, f"status={st} ok={(body or {}).get('ok')} decision_id={did} {extra}")
        ids[op] = did
    report("decision_ids distinct", len({v for v in ids.values() if v}) == len([v for v in ids.values() if v]),
           str(ids))

    # 3. GET /healthz
    st, body, _ = req("GET", "/healthz")
    report("instance-1 GET /healthz", st == 200 and (body or {}).get("engine_available") is True,
           f"status={st} keys={sorted((body or {}).keys())}")
    report("healthz surfaces learned fields",
           isinstance(body, dict) and "learned_module_performance" in body and "feedback_state" in body,
           f"learned_module_performance={'learned_module_performance' in (body or {})} feedback_state={'feedback_state' in (body or {})}")

    # 4. startup health fields
    fs = (health1 or {}).get("feedback_state") or {}
    report("instance-1 startup health fields",
           health1.get("feedback_available") is True
           and "learned_module_performance" in health1
           and "underperforming_modules" in health1
           and fs.get("path") == str(STATE)
           and fs.get("restored") is None,
           f"feedback_available={health1.get('feedback_available')} restored={fs.get('restored')} lmp={health1.get('learned_module_performance')}")

    # 5. feedback on D1
    d1 = ids["predict"]
    st, body, _ = req("POST", "/api/v1/ciaas/feedback",
                      body={"payload": True, "metadata": {"decision_id": d1}})
    res = (body or {}).get("result") or {}
    report("feedback on real decision_id", st == 200 and (body or {}).get("ok") is True
           and isinstance(res.get("calibration_score"), (int, float))
           and isinstance(res.get("learning_signal"), (int, float))
           and isinstance(res.get("recommendations"), list),
           f"status={st} calibration={res.get('calibration_score')} signal={res.get('learning_signal')}")

    # 6. state file persisted
    if STATE.exists():
        snap = json.loads(STATE.read_text())
        mp = snap.get("model_parameters") or {}
        cnt = (snap.get("counts") or {}).get("decisions")
        report("state file persisted", bool(mp) and cnt and cnt >= 4,
               f"model_parameters={len(mp)} counts.decisions={cnt}")
    else:
        report("state file persisted", False, "file missing")

    # 7. garbage decision id
    st, body, _ = req("POST", "/api/v1/ciaas/feedback",
                      body={"payload": True, "metadata": {"decision_id": "totally-bogus-id"}})
    msg = ((body or {}).get("error") or {}).get("message", "")
    report("garbage decision_id fails closed", st != 500 and (body or {}).get("ok") is False
           and "not found" in msg.lower(),
           f"status={st} msg={msg!r}")

    # 8. malformed JSON
    st, body, _ = req("POST", "/api/v1/ciaas/predict", raw=b"{not valid json",
                      )
    report("malformed JSON -> 4xx not 5xx", 400 <= st < 500,
           f"status={st} body={body}")

    # 9. missing tenant header
    st, body, _ = req("POST", "/api/v1/ciaas/predict", body=payload, tenant=None)
    report("missing tenant -> 401", st == 401, f"status={st}")

    # 10. replay already-processed decision id
    st, body, _ = req("POST", "/api/v1/ciaas/feedback",
                      body={"payload": True, "metadata": {"decision_id": d1}})
    msg = ((body or {}).get("error") or {}).get("message", "")
    report("double-process decision_id rejected", (body or {}).get("ok") is False
           and "already been processed" in msg, f"status={st} msg={msg!r}")

    kill(proc1)

    print("=" * 70)
    print("INSTANCE 2 — restart, same state path")
    print("=" * 70)
    proc2, health2, lines2 = boot(STATE)
    if health2 is None:
        report("instance-2 boot", False, "no STARTUP_HEALTH; output: " + " | ".join(lines2[-5:]))
        kill(proc2)
        return 1
    report("instance-2 boot", True)

    # 11. restored state
    fs2 = (health2 or {}).get("feedback_state") or {}
    rst = fs2.get("restored") or {}
    lmp2 = health2.get("learned_module_performance") or {}
    report("instance-2 learned state restored",
           isinstance(rst, dict) and rst.get("restored") is True
           and (rst.get("model_parameters") or 0) > 0 and bool(lmp2),
           f"restored={rst} learned_params={len(lmp2)}")

    # 12. healthz after restart
    st, body, _ = req("GET", "/healthz")
    report("instance-2 GET /healthz", st == 200 and (body or {}).get("engine_available") is True,
           f"status={st}")

    # 13. old decision id must NOT resurrect
    st, body, _ = req("POST", "/api/v1/ciaas/feedback",
                      body={"payload": True, "metadata": {"decision_id": d1}})
    msg = ((body or {}).get("error") or {}).get("message", "")
    report("pre-restart decision_id rejected (fail-closed replay)",
           (body or {}).get("ok") is False and "not found" in msg.lower(),
           f"status={st} msg={msg!r}")

    # 14. loop still works post-restore
    st, body, _ = req("POST", "/api/v1/ciaas/predict", body=payload)
    d5 = (body or {}).get("decision_id")
    st2, body2, _ = req("POST", "/api/v1/ciaas/feedback",
                        body={"payload": True, "metadata": {"decision_id": d5}})
    report("post-restart voyage closes", st == 200 and bool(d5)
           and st2 == 200 and (body2 or {}).get("ok") is True,
           f"new_did={d5} feedback_status={st2} ok={(body2 or {}).get('ok')}")

    kill(proc2)

    print("=" * 70)
    fails = [n for n, p in results if not p]
    print(f"TOTAL: {len(results) - len(fails)} passed, {len(fails)} failed")
    for n in fails:
        print("  FAILED: " + n)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
