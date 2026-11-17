# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Console status computed from the ledger, and nothing else.

Hashrate is the sum of executed candidates divided by the sum of device time
over the ``work`` records in the trailing window; it is "not measured" when no
device work was recorded there. Accepted and rejected shares count only pool
replies (``pool_response`` records); a submitted share without a reply is
"awaiting or unacknowledged", never accepted. Units aborted because their job
went stale (or at shutdown) are counted from ``unit_aborted_*`` records; their
partial work is not in any ``work`` record, so it never reaches hashrate.
The hashrate cap is the configured ceiling recorded at ``session_start`` (and
``hashrate_cap_changed``); it is shown as a ceiling, never as a rate, and
``hashrate_cap_window`` records only say how often it held work back.

When several routes mine at once (``executed_routes`` in ``session_start``),
each route's measured rate is its executed candidates over its own device
time, and the total is the sum of those per-route rates; a route that is not
running is listed with the reason pre-flight recorded (``degraded_reason``).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from hyba_mine.igpu import route_label
from hyba_mine.pools import POOL_CATALOG

TRAILING_SECONDS = 60
STALE_AFTER_SECONDS = 180


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def format_rate(hps: Optional[float]) -> str:
    if hps is None:
        return "not measured"
    for unit, scale in (("EH/s", 1e18), ("PH/s", 1e15), ("TH/s", 1e12), ("GH/s", 1e9), ("MH/s", 1e6), ("kH/s", 1e3)):
        if hps >= scale:
            return f"{hps / scale:.3g} {unit}"
    return f"{hps:.3g} H/s"


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h {minutes:02d}m {secs:02d}s"


def summarize(records: Iterable[dict], now: Optional[datetime] = None, trailing: int = TRAILING_SECONDS) -> dict:
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(seconds=trailing)
    session = None
    stop = None
    pool = None
    pool_down = None
    vmask = None
    job = None
    difficulty = None
    last_reply = None
    last_ts = None
    preflight = None
    fault = None
    switch = None
    count = 0
    submitted: dict = {}
    replies: dict = {}
    unacknowledged: set = set()
    dropped = 0
    aborted_stale = aborted_shutdown = 0
    cap: Optional[dict] = None
    cap_window = [0, 0, 0, 0]  # throttled_ns, waits, clamped units, refunded hashes
    trailing_work: dict = {}
    compute_units: dict = {}
    routes_stopped: dict = {}
    session_work = [0, 0]
    for record in records:
        count += 1
        kind = record.get("kind")
        data = record.get("data") or {}
        ts = record.get("ts")
        last_ts = ts or last_ts
        if kind == "session_start":
            session, stop, fault = record, None, None
            submitted, replies, unacknowledged, dropped = {}, {}, set(), 0
            aborted_stale = aborted_shutdown = 0
            cap = dict(data["hashrate_cap"]) if isinstance(data.get("hashrate_cap"), dict) else None
            cap_window = [0, 0, 0, 0]
            session_work = [0, 0]
            trailing_work = {}
            compute_units = {}
            routes_stopped = {}
            pool = pool_down = job = difficulty = last_reply = vmask = None
        elif kind == "session_stop":
            stop = record
        elif kind == "preflight":
            preflight = record
        elif kind == "pool_connected":
            pool, pool_down, vmask = record, None, None
        elif kind == "version_mask":
            vmask = record
        elif kind == "pool_disconnected":
            pool_down = record
        elif kind == "job":
            job = record
        elif kind == "difficulty":
            difficulty = record
        elif kind == "work":
            session_work[0] += int(data.get("executed", 0))
            session_work[1] += int(data.get("device_ns", 0))
            if ts and parse_ts(ts) >= horizon:
                key = (data.get("node"), data.get("route"))
                entry = trailing_work.setdefault(key, [0, 0, 0])
                entry[0] += int(data.get("executed", 0))
                entry[1] += int(data.get("device_ns", 0))
                entry[2] += int(data.get("span_ns", 0))
                if data.get("compute_unit"):
                    compute_units[key] = data.get("compute_unit")
        elif kind == "route_stopped":
            routes_stopped[data.get("route")] = data
        elif kind == "share_submitted":
            submitted[data.get("share_id")] = record
        elif kind == "pool_response":
            share_id = data.get("share_id")
            if share_id not in replies:
                replies[share_id] = record
            last_reply = record
        elif kind == "share_unacknowledged":
            unacknowledged.add(data.get("share_id"))
        elif kind in ("share_stale_dropped", "share_duplicate_dropped"):
            dropped += 1
        elif kind == "unit_aborted_stale":
            aborted_stale += 1
        elif kind == "unit_aborted_shutdown":
            aborted_shutdown += 1
        elif kind == "hashrate_cap_changed":
            if cap is not None:
                cap["cap_h_s"] = data.get("to_h_s")
                cap["changed_at"] = ts
        elif kind == "hashrate_cap_window":
            if ts and parse_ts(ts) >= horizon:
                cap_window[0] += int(data.get("throttled_ns", 0))
                cap_window[1] += int(data.get("throttle_waits", 0))
                cap_window[2] += int(data.get("clamped_units", 0))
                cap_window[3] += int(data.get("refunded_hashes", 0))
        elif kind == "device_fault":
            fault = record
        elif kind in ("pool_switch_applied", "pool_switch_refused", "pool_switch_requested"):
            switch = record
    accepted = sum(1 for r in replies.values() if r["data"].get("accepted") is True)
    rejected = sum(1 for r in replies.values() if r["data"].get("accepted") is not True)
    awaiting = sum(1 for share_id in submitted if share_id not in replies)
    lanes = []
    total_rate = None
    total_effective = None
    for (node, route), (executed, device_ns, span_ns) in sorted(trailing_work.items(), key=lambda item: str(item[0])):
        if executed and device_ns:
            rate = executed / (device_ns / 1e9)
            effective = executed / (span_ns / 1e9) if span_ns else None
            total_rate = (total_rate or 0.0) + rate
            if effective is not None:
                total_effective = (total_effective or 0.0) + effective
            lanes.append({"node": node, "route": route, "label": route_label(route),
                          "compute_unit": compute_units.get((node, route)),
                          "executed": executed, "device_seconds": device_ns / 1e9, "hashrate_hs": rate,
                          "wall_seconds": span_ns / 1e9, "effective_hs": effective,
                          "busy_fraction": min(1.0, device_ns / span_ns) if span_ns else None})
    running = session is not None and stop is None
    age = (now - parse_ts(last_ts)).total_seconds() if last_ts else None
    state = "NO SESSION"
    if session is not None:
        if stop is not None:
            state = "STOPPED"
        elif fault is not None:
            state = "DEVICE FAULT"
        elif age is not None and age > STALE_AFTER_SECONDS:
            state = "NO RECENT ACTIVITY"
        elif pool is None or pool_down is not None:
            state = "CONNECTING"
        elif job is None:
            state = "WAITING FOR A JOB"
        else:
            state = "MINING"
    sdata = (session or {}).get("data", {})
    executed_routes = sdata.get("executed_routes") or ([sdata["executed_route"]] if sdata.get("executed_route") else [])
    pdata = (pool or {}).get("data", {})
    jdata = (job or {}).get("data", {})
    negotiation = pdata.get("version_negotiation")
    version_rolling = {
        # None (not a false "off") for ledgers written before version rolling was recorded.
        "active": pdata.get("version_rolling"),
        "mask": vmask["data"].get("granted_mask") if vmask is not None else pdata.get("version_mask"),
        "negotiation": negotiation.get("outcome") if isinstance(negotiation, dict) else None,
        "basis": "pool reply to mining.configure / mining.set_version_mask",
    }
    pool_id = pdata.get("pool") or sdata.get("pool")
    cap_rate = cap.get("cap_h_s") if cap is not None else None
    cap_summary = None
    if session is not None and isinstance(cap_rate, int) and not isinstance(cap_rate, bool):
        cap_summary = {
            "cap_h_s": cap_rate,
            "display": format_rate(cap_rate),
            "kind": "ceiling",
            "basis": cap.get("basis"),
            "scope": cap.get("scope"),
            "changed_at": cap.get("changed_at"),
            "throttled_seconds": cap_window[0] / 1e9,
            "throttle_waits": cap_window[1],
            "clamped_units": cap_window[2],
            "refunded_hashes": cap_window[3],
            "bound_in_window": cap_window[1] > 0 or cap_window[2] > 0,
            "window_seconds": trailing,
        }
    return {
        "source": "ledger",
        "records": count,
        "observed_at": now.isoformat().replace("+00:00", "Z"),
        "state": state,
        "last_activity_seconds": age,
        "session": None if session is None else {
            "started_at": session.get("ts"),
            "uptime_seconds": (now - parse_ts(session["ts"])).total_seconds() if running else None,
            "stopped_at": stop.get("ts") if stop else None,
            "stop_reason": (stop or {}).get("data", {}).get("reason"),
            "exit_code": (stop or {}).get("data", {}).get("exit_code"),
            "node": sdata.get("node"),
        },
        "route": None if session is None else {
            "requested": sdata.get("requested_route"),
            "executed": sdata.get("executed_route"),
            "executed_routes": executed_routes,
            "label": " + ".join(route_label(r) for r in executed_routes) if executed_routes else None,
            "degraded": bool(sdata.get("degraded")),
            "degraded_reason": sdata.get("degraded_reason"),
            "unavailable_routes": sdata.get("unavailable_routes") or [],
            "routes_stopped": list(routes_stopped.values()),
            "fallback_reason": sdata.get("fallback_reason"),
            "requested_backend": sdata.get("requested_backend"),
            "preference": sdata.get("preference"),
            "detected_backends": sdata.get("detected_backends"),
            "executed_backend": sdata.get("executed_backend"),
            "executed_backends": sdata.get("executed_backends")
            or ([sdata["executed_backend"]] if sdata.get("executed_backend") else []),
        },
        "pool": None if pool_id is None else {
            "pool_id": pool_id,
            "name": POOL_CATALOG[pool_id].name if pool_id in POOL_CATALOG else pool_id,
            "endpoint": pdata.get("endpoint"),
            "tls": pdata.get("tls"),
            "connected": pool is not None and pool_down is None,
            "login_fingerprint": pdata.get("login_fingerprint"),
            "worker": pdata.get("worker"),
            "version_rolling": version_rolling,
        },
        "hashrate": {
            "hashrate_hs": total_rate,
            "display": format_rate(total_rate),
            "basis": f"executed candidates / device time, work records in the last {trailing} s",
            "effective_hs": total_effective,
            "effective_display": format_rate(total_effective),
            "effective_basis": "executed candidates / wall time covered by those work records",
            "window_seconds": trailing,
            "lanes": lanes,
            "session_executed": session_work[0],
            "session_device_seconds": session_work[1] / 1e9,
        },
        "hashrate_cap": cap_summary,
        "job": None if job is None else {
            "job_id": jdata.get("job_id"),
            "received_at": jdata.get("received_at") or job.get("ts"),
            "clean_jobs": jdata.get("clean_jobs"),
            "difficulty": (difficulty or {}).get("data", {}).get("difficulty") or jdata.get("difficulty"),
        },
        "shares": {
            "submitted": len(submitted),
            "accepted": accepted,
            "rejected": rejected,
            "awaiting_or_unacknowledged": awaiting,
            "unacknowledged": len(unacknowledged - set(replies)),
            "dropped_before_submit": dropped,
            "basis": "accepted and rejected count pool replies only",
        },
        "units": {
            "aborted_stale": aborted_stale,
            "aborted_shutdown": aborted_shutdown,
            "basis": "unit_aborted_* ledger records; partial work is not counted in hashrate",
        },
        "last_pool_reply": None if last_reply is None else {
            "at": last_reply.get("ts"),
            "accepted": last_reply["data"].get("accepted"),
            "reply": last_reply["data"].get("reply"),
        },
        "device_fault": None if fault is None else fault.get("data"),
        "last_preflight": None if preflight is None else {
            "at": preflight.get("ts"),
            "passed": preflight["data"].get("passed"),
            "failed_checks": [c["name"] for c in preflight["data"].get("checks", []) if not c.get("passed")],
        },
        "last_pool_switch": None if switch is None else {"at": switch.get("ts"), "kind": switch.get("kind"), **switch.get("data", {})},
    }


def render_text(summary: dict) -> str:
    lines = [f"HYBA Mine status (every value from the local ledger, {summary['records']} records)"]
    age = summary.get("last_activity_seconds")
    lines.append(f"  State        {summary['state']}" + (f" (last ledger record {age:.0f} s ago)" if age is not None else ""))
    session = summary.get("session")
    if session:
        if session.get("uptime_seconds") is not None:
            lines.append(f"  Uptime       {format_duration(session['uptime_seconds'])} since {session['started_at']}")
        elif session.get("stopped_at"):
            lines.append(f"  Stopped      {session['stopped_at']}: {session.get('stop_reason')} (exit {session.get('exit_code')})")
    pool = summary.get("pool")
    if pool:
        worker = f", worker '{pool['worker']}'" if pool.get("worker") else ""
        tls = "TLS" if pool.get("tls") else "plain TCP"
        endpoint = pool.get("endpoint") or "not connected"
        lines.append(f"  Pool         {pool['name']} - {endpoint} ({tls}) - login {pool.get('login_fingerprint')}{worker}")
        rolling = pool.get("version_rolling") or {}
        if rolling.get("active") is True:
            lines.append(f"  Version roll granted mask {rolling.get('mask')} (BIP310; widens the search space, not the hashrate)")
        elif rolling.get("active") is False:
            lines.append(f"  Version roll off ({rolling.get('negotiation') or 'not negotiated'})")
    route = summary.get("route")
    if route:
        reason = route.get("fallback_reason") or "none"
        lines.append(f"  Route        requested {route['requested']} -> executed {route['label']} (fallback_reason: {reason})")
        if route.get("degraded"):
            lines.append(f"  Degraded     single route: {route.get('degraded_reason')}")
        if route.get("executed_backend"):
            detected = ", ".join(route.get("detected_backends") or [])
            lines.append(f"  Backend      {route['executed_backend']} (requested {route.get('requested_backend')}, "
                         f"prefer {route.get('preference')}; detected {detected})")
    rate = summary["hashrate"]
    if rate.get("hashrate_hs") is None:
        lines.append("  Hashrate     not measured (no device work recorded in the last "
                     f"{rate.get('window_seconds', 60)} s)")
    else:
        lines.append(f"  Hashrate     {rate['display']} measured ({rate['basis']})")
    if rate.get("effective_hs") is not None:
        lines.append(f"               {rate['effective_display']} effective ({rate['effective_basis']})")
    if len(rate.get("lanes") or []) > 1:
        for lane in rate["lanes"]:
            where = f" on {lane['compute_unit']}" if lane.get("compute_unit") else ""
            lines.append(f"  Lane         {lane['label']}{where}: {format_rate(lane['hashrate_hs'])} measured")
    cap = summary.get("hashrate_cap")
    if cap:
        line = f"  Hashrate cap {cap['display']} ceiling on work this process schedules (configured, not measured)"
        if cap.get("bound_in_window"):
            line += (f" - throttled {cap['throttled_seconds']:.1f} s, {cap['clamped_units']} units shortened"
                     f" in the last {cap['window_seconds']} s")
        lines.append(line)
    elif session:
        lines.append("  Hashrate cap not recorded for this session")
    job = summary.get("job")
    if job:
        lines.append(f"  Current job  {job['job_id']} received {job['received_at']} (clean_jobs: {job['clean_jobs']}), share difficulty {job['difficulty']}")
    else:
        lines.append("  Current job  none received (no job, no hashing)")
    shares = summary["shares"]
    lines.append(
        f"  Shares       submitted {shares['submitted']} | accepted {shares['accepted']} | rejected {shares['rejected']}"
        f" | awaiting/unacknowledged {shares['awaiting_or_unacknowledged']}  (pool replies only)"
    )
    units = summary.get("units") or {}
    if units.get("aborted_stale") or units.get("aborted_shutdown"):
        lines.append(f"  Aborted      {units['aborted_stale']} unit(s) on stale jobs, {units['aborted_shutdown']} at shutdown"
                     " (partial work not counted in hashrate)")
    reply = summary.get("last_pool_reply")
    if reply:
        verdict = "accepted" if reply.get("accepted") else "rejected"
        lines.append(f"  Last reply   {reply['at']} {verdict}: {json.dumps(reply.get('reply'), sort_keys=True)}")
    if summary.get("device_fault"):
        lines.append(f"  Device fault {summary['device_fault'].get('reason')}")
    pre = summary.get("last_preflight")
    if pre:
        failed = ", ".join(pre["failed_checks"]) or "none"
        lines.append(f"  Pre-flight   {'PASSED' if pre['passed'] else 'FAILED'} at {pre['at']} (failed: {failed})")
    return "\n".join(lines)
