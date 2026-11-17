# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Optional start-at-login: launchd (macOS), Task Scheduler (Windows), systemd --user (Linux).

The agent (``~/Library/LaunchAgents/ae.hybadata.mine.plist``) runs
``scripts/mine/run.sh``, which always runs the pre-flight before mining.
``KeepAlive.SuccessfulExit = false`` restarts the miner after a crash or a
failed pre-flight (no sooner than every two minutes) but not after a clean
stop, so ``hyba-mine stop`` stays stopped until the next login or
``hyba-mine autostart enable``.

Windows: a per-user Task Scheduler task (``HYBA-Mine``) with a logon trigger for
this account's SID, least privilege, the interactive token, no stored password
and restart-on-failure (every 2 minutes, 3 times). Linux: a ``systemd --user``
service with ``Restart=on-failure``. Both run ``python -m hyba_mine.launch``,
which runs the pre-flight before mining. No administrator rights are needed.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Optional

from hyba_mine import portable
from hyba_mine.paths import (
    LAUNCH_AGENT_LABEL,
    Layout,
    ensure_private_dir,
    is_macos,
    launch_agent_path,
    systemd_user_unit_path,
    write_private_file,
)

LAUNCHCTL = "/bin/launchctl"
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def plist_payload(run_script: Path, layout: Layout) -> dict:
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/bin/bash", str(run_script)],
        "WorkingDirectory": str(run_script.resolve().parent.parent.parent),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 120,
        "StandardOutPath": str(layout.logs / "launchd.out.log"),
        "StandardErrorPath": str(layout.logs / "launchd.err.log"),
        "EnvironmentVariables": {
            "PATH": DEFAULT_PATH,
            "HYBA_MINE_HOME": str(layout.home),
            "HYBA_MINE_LOG_DIR": str(layout.logs),
            "HYBA_MINE_VENV": os.environ.get("HYBA_MINE_VENV", str(Path.home() / ".hyba-mine" / "venv")),
        },
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([LAUNCHCTL, *args], capture_output=True, text=True, timeout=30, check=False)


def _enable_macos(run_script: Path, layout: Layout, *, start: bool = True) -> Path:
    if not run_script.exists():
        raise FileNotFoundError(f"run script not found: {run_script}")
    layout.prepare()
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(plist_payload(run_script, layout)))
    os.chmod(path, 0o644)
    if not start:
        return path
    _launchctl("bootout", f"{_domain()}/{LAUNCH_AGENT_LABEL}")
    done = _launchctl("bootstrap", _domain(), str(path))
    if done.returncode != 0:
        raise RuntimeError(f"launchctl bootstrap failed: {done.stderr.strip() or done.returncode}")
    return path


def _disable_macos() -> bool:
    _launchctl("bootout", f"{_domain()}/{LAUNCH_AGENT_LABEL}")
    path = launch_agent_path()
    if path.exists():
        path.unlink()
        return True
    return False


def _status_macos() -> dict:
    path = launch_agent_path()
    loaded = _launchctl("print", f"{_domain()}/{LAUNCH_AGENT_LABEL}").returncode == 0
    return {"platform": "macos", "mechanism": "launchd", "label": LAUNCH_AGENT_LABEL, "plist": str(path),
            "installed": path.exists(), "loaded": bool(loaded)}


# ------------------------------------------------------------ shared helpers
Runner = Callable[[list], subprocess.CompletedProcess]
WINDOWS_TASK_NAME = "HYBA-Mine"
SYSTEMD_UNIT = "hyba-mine.service"
TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
SCHTASKS = str(Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "schtasks.exe")


class AutostartUnsupported(RuntimeError):
    pass


def _run(argv: list) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=30, check=False)


def launcher_python(executable: str = sys.executable) -> str:
    """pythonw.exe on Windows (no console window at login) when it sits beside python.exe."""
    if portable.IS_WINDOWS:
        candidate = Path(executable).with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return executable


def launcher_args(layout: Layout) -> list:
    return ["-m", "hyba_mine.launch", "--home", str(layout.home), "--logs", str(layout.logs)]


def _platform(platform_id: Optional[str]) -> str:
    return platform_id or portable.platform_id()


# ------------------------------------------------------------------ Windows
def _q(tag: str) -> str:
    return "{" + TASK_NS + "}" + tag


def windows_task_xml(layout: Layout, python: str, sid: str) -> bytes:
    ET.register_namespace("", TASK_NS)
    task = ET.Element(_q("Task"), {"version": "1.2"})
    info = ET.SubElement(task, _q("RegistrationInfo"))
    ET.SubElement(info, _q("Description")).text = "Starts HYBA Mine at logon; the pre-flight runs before any mining."
    trigger = ET.SubElement(ET.SubElement(task, _q("Triggers")), _q("LogonTrigger"))
    ET.SubElement(trigger, _q("Enabled")).text = "true"
    ET.SubElement(trigger, _q("UserId")).text = sid
    principal = ET.SubElement(ET.SubElement(task, _q("Principals")), _q("Principal"), {"id": "Author"})
    ET.SubElement(principal, _q("UserId")).text = sid
    ET.SubElement(principal, _q("LogonType")).text = "InteractiveToken"
    ET.SubElement(principal, _q("RunLevel")).text = "LeastPrivilege"
    settings = ET.SubElement(task, _q("Settings"))
    for tag, value in (("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
                       ("StopIfGoingOnBatteries", "false"), ("ExecutionTimeLimit", "PT0S")):
        ET.SubElement(settings, _q(tag)).text = value
    restart = ET.SubElement(settings, _q("RestartOnFailure"))
    ET.SubElement(restart, _q("Interval")).text = "PT2M"
    ET.SubElement(restart, _q("Count")).text = "3"
    ET.SubElement(settings, _q("Enabled")).text = "true"
    ET.SubElement(settings, _q("Hidden")).text = "false"
    action = ET.SubElement(ET.SubElement(task, _q("Actions"), {"Context": "Author"}), _q("Exec"))
    ET.SubElement(action, _q("Command")).text = python
    ET.SubElement(action, _q("Arguments")).text = subprocess.list2cmdline(launcher_args(layout))
    ET.SubElement(action, _q("WorkingDirectory")).text = str(layout.home)
    body = ET.tostring(task, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-16"?>\n' + body).encode("utf-16")


def windows_task_commands(xml_path: Path, *, start: bool) -> list:
    # Never /RU, /RP or /RL HIGHEST: the task runs as this user, unelevated, with no stored password.
    commands = [[SCHTASKS, "/Create", "/TN", WINDOWS_TASK_NAME, "/XML", str(xml_path), "/F"]]
    if start:
        commands.append([SCHTASKS, "/Run", "/TN", WINDOWS_TASK_NAME])
    return commands


def _windows_status(runner: Runner) -> dict:
    done = runner([SCHTASKS, "/Query", "/TN", WINDOWS_TASK_NAME, "/XML"])
    result = {"platform": "windows", "mechanism": "task_scheduler", "task": WINDOWS_TASK_NAME,
              "installed": done.returncode == 0, "enabled": None, "matches_expected": None}
    if done.returncode != 0:
        return result
    try:
        root = ET.fromstring(done.stdout.split("?>", 1)[-1].strip())
        ns = {"t": TASK_NS}
        enabled = root.findtext("t:Settings/t:Enabled", default="true", namespaces=ns)
        command = root.findtext("t:Actions/t:Exec/t:Command", default="", namespaces=ns)
        arguments = root.findtext("t:Actions/t:Exec/t:Arguments", default="", namespaces=ns)
        result["enabled"] = enabled.strip().lower() == "true"
        result["matches_expected"] = command == launcher_python() and "hyba_mine.launch" in arguments
    except ET.ParseError:
        result["detail"] = "the installed task definition could not be read"
    return result


# -------------------------------------------------------------------- Linux
def systemd_unit_text(layout: Layout, python: str) -> str:
    exec_start = " ".join(shlex.quote(part) for part in [python, *launcher_args(layout)])
    return (
        "[Unit]\nDescription=HYBA Mine (pre-flight runs before any mining)\n\n"
        "[Service]\nType=simple\n"
        f"ExecStart={exec_start}\n"
        f'Environment="HYBA_MINE_HOME={layout.home}"\n'
        f'Environment="HYBA_MINE_LOG_DIR={layout.logs}"\n'
        "Restart=on-failure\nRestartSec=120\nKillSignal=SIGTERM\nTimeoutStopSec=30\n\n"
        "[Install]\nWantedBy=default.target\n"
    )


def _systemctl() -> str:
    return shutil.which("systemctl") or "/usr/bin/systemctl"


def systemd_commands(action: str, *, start: bool = False) -> list:
    ctl = [_systemctl(), "--user"]
    if action == "enable":
        return [ctl + ["daemon-reload"], ctl + ["enable", *(["--now"] if start else []), SYSTEMD_UNIT]]
    if action == "disable":
        return [ctl + ["disable", "--now", SYSTEMD_UNIT]]
    raise ValueError(action)


def _run_all(commands: list, runner: Runner, what: str) -> None:
    for argv in commands:
        done = runner(argv)
        if done.returncode != 0:
            verb = argv[1] if what == "schtasks" else argv[2]
            raise RuntimeError(f"{what} {verb} failed (exit {done.returncode}): {(done.stderr or '').strip()}")


def _unit_path(unit_dir: Optional[Path]) -> Path:
    return (unit_dir / SYSTEMD_UNIT) if unit_dir else systemd_user_unit_path()


# ------------------------------------------------------------ entry points
def _is_mac(platform_id: Optional[str]) -> bool:
    return platform_id == "macos" or (platform_id is None and is_macos())


def enable(run_script: Path, layout: Layout, *, start: bool = True, runner: Optional[Runner] = None,
           platform_id: Optional[str] = None, python: Optional[str] = None, sid: Optional[str] = None,
           unit_dir: Optional[Path] = None) -> Path:
    if _is_mac(platform_id):
        return _enable_macos(run_script, layout, start=start)
    plat = _platform(platform_id)
    runner = runner or _run
    python = python or launcher_python()
    if plat == "windows":
        layout.prepare()
        sid = sid or str(portable.user_identity().value)
        path = layout.autostart_dir / "hyba-mine-task.xml"
        ensure_private_dir(path.parent)
        write_private_file(path, windows_task_xml(layout, python, sid))
        _run_all(windows_task_commands(path, start=start), runner, "schtasks")
        return path
    if plat == "linux":
        layout.prepare()
        path = _unit_path(unit_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(systemd_unit_text(layout, python), encoding="utf-8")
        os.chmod(path, 0o600)
        _run_all(systemd_commands("enable", start=start), runner, "systemctl")
        return path
    raise AutostartUnsupported(f"start-at-login is not available on {plat}")


def disable(*, runner: Optional[Runner] = None, platform_id: Optional[str] = None,
            unit_dir: Optional[Path] = None) -> bool:
    if _is_mac(platform_id):
        return _disable_macos()
    plat = _platform(platform_id)
    runner = runner or _run
    if plat == "windows":
        return runner([SCHTASKS, "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"]).returncode == 0
    if plat == "linux":
        path = _unit_path(unit_dir)
        runner(systemd_commands("disable")[0])
        existed = path.exists()
        if existed:
            path.unlink()
        runner([_systemctl(), "--user", "daemon-reload"])
        return existed
    return False


def status(*, runner: Optional[Runner] = None, platform_id: Optional[str] = None,
           unit_dir: Optional[Path] = None) -> dict:
    if _is_mac(platform_id):
        return _status_macos()
    plat = _platform(platform_id)
    runner = runner or _run
    if plat == "windows":
        return _windows_status(runner)
    if plat == "linux":
        enabled = runner([_systemctl(), "--user", "is-enabled", SYSTEMD_UNIT]).returncode == 0
        active = runner([_systemctl(), "--user", "is-active", SYSTEMD_UNIT]).returncode == 0
        path = _unit_path(unit_dir)
        return {"platform": "linux", "mechanism": "systemd_user", "unit": str(path),
                "installed": path.exists(), "enabled": enabled, "active": active}
    return {"platform": plat, "mechanism": "none", "installed": False}
