#!/usr/bin/env python3
"""
HYBA Production Port Diagnostic & Process Terminator
====================================================
Diagnoses port conflicts (port 8000, 3000, 5173, etc.) using OS socket inspection
and netstat. Supports graceful termination of dangling processes or automatic
fallback to alternative ports (HYBA_API_PORT=8001 / 8080).
"""

import sys
import socket
import subprocess
from typing import List, Optional, Tuple


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a TCP port is currently occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_pids_for_port(port: int) -> List[int]:
    """Find PIDs listening on a port using netstat (Windows) or lsof (POSIX)."""
    pids = set()
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                f"netstat -ano | findstr :{port}", shell=True, text=True, stderr=subprocess.DEVNULL
            )
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    pid = int(parts[-1])
                    if pid > 0:
                        pids.add(pid)
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            output = subprocess.check_output(
                ["lsof", "-t", f"-i:{port}"], text=True, stderr=subprocess.DEVNULL
            )
            for line in output.strip().splitlines():
                if line.isdigit():
                    pids.add(int(line))
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return sorted(list(pids))


def terminate_pid(pid: int, force: bool = True) -> bool:
    """Terminate a process by PID."""
    try:
        if sys.platform == "win32":
            flag = "/F" if force else ""
            subprocess.run(
                f"taskkill {flag} /PID {pid}",
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            sig = "-9" if force else "-15"
            subprocess.run(
                ["kill", sig, str(pid)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        return True
    except subprocess.CalledProcessError:
        return False


def diagnose_and_clean_ports(
    ports: List[int] = [8000, 3000, 5173], kill: bool = False, fallback_env: str = "HYBA_API_PORT"
) -> Tuple[int, Optional[int]]:
    """
    Diagnose target ports. If port 8000 is occupied and kill is False,
    determine first available fallback port (e.g., 8001, 8080).
    """
    print(f"[*] Diagnosing ports: {ports}")
    first_target = ports[0]
    assigned_port = first_target

    for port in ports:
        occupied = is_port_in_use(port)
        status = "OCCUPIED" if occupied else "AVAILABLE"
        print(f"  - Port {port}: [{status}]")
        if occupied:
            pids = find_pids_for_port(port)
            print(f"    PIDs holding port {port}: {pids}")
            if kill and pids:
                for pid in pids:
                    print(f"    Terminating PID {pid}...")
                    success = terminate_pid(pid, force=True)
                    print(f"    PID {pid} terminated: {success}")
                # Verify release
                if not is_port_in_use(port):
                    print(f"    Port {port} is now FREE.")
                else:
                    print(f"    Warning: Port {port} remains occupied after kill attempt.")

    # Determine runtime port
    if is_port_in_use(first_target):
        fallbacks = [8001, 8080, 8888]
        found = None
        for fb in fallbacks:
            if not is_port_in_use(fb):
                found = fb
                break
        if found:
            print(f"[*] Primary port {first_target} is occupied. Recommended fallback: {found}")
            print(f"    Export: set {fallback_env}={found}")
            assigned_port = found
        else:
            print(
                f"[!] Warning: Neither primary port {first_target} nor common fallbacks are free."
            )
    else:
        print(f"[✓] Primary port {first_target} is clear for binding.")

    return first_target, assigned_port


if __name__ == "__main__":
    kill_flag = "--kill" in sys.argv or "-k" in sys.argv
    diagnose_and_clean_ports(ports=[8000, 3000, 5173], kill=kill_flag)
