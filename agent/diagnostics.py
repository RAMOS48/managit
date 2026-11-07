import ipaddress
import logging
import platform
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil

log = logging.getLogger("agent")

MAX_OUTPUT = 4000
# Must start and end with a letter or digit, so a value can never start with "-"
HOSTNAME_RE = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")


class BadParameter(Exception):
    pass


def check_host(value) -> str:
    if not isinstance(value, str):
        raise BadParameter("host must be text")
    host = value.strip()
    if not host or len(host) > 253:
        raise BadParameter("host is empty or too long")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if not HOSTNAME_RE.fullmatch(host):
        raise BadParameter("host is not a valid hostname or IP address")
    return host


def check_port(value) -> int:
    if isinstance(value, bool):
        raise BadParameter("port must be a number")
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not 1 <= value <= 65535:
        raise BadParameter("port must be between 1 and 65535")
    return value


def _result(success: bool, summary: str, error: bool = False) -> dict:
    return {"success": success, "summary": summary[:MAX_OUTPUT], "error": error}


def _gb(value: float) -> str:
    return f"{value / 1024 ** 3:.1f} GB"


def do_ping(host: str) -> dict:
    if platform.system() == "Windows":
        command = ["ping", "-n", "4", "-w", "2000", host]
    else:
        command = ["ping", "-c", "4", "-W", "2", host]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return _result(False, f"Ping to {host} timed out")
    except FileNotFoundError:
        return _result(False, "The ping command is not available on this device", error=True)

    output = (proc.stdout or proc.stderr or "").strip()
    reachable = proc.returncode == 0 and "ttl=" in output.lower()
    headline = f"{host} is reachable" if reachable else f"{host} is NOT reachable"
    return _result(reachable, headline + "\n\n" + output)


def do_dns(host: str) -> dict:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return _result(False, f"Could not resolve {host}: {exc}")
    addresses = sorted({info[4][0] for info in infos})
    return _result(True, f"{host} resolves to:\n" + "\n".join(addresses))


def do_tcp(host: str, port: int) -> dict:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=5):
            elapsed = (time.monotonic() - started) * 1000
        return _result(True, f"{host}:{port} is open (connected in {elapsed:.0f} ms)")
    except OSError as exc:
        return _result(False, f"{host}:{port} is closed or unreachable: {exc}")


def do_system_info(agent_version: str) -> dict:
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = str(datetime.now() - boot).split(".")[0]
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor)
    lines = [
        f"Hostname: {socket.gethostname()}",
        f"Operating system: {platform.platform()}",
        f"Architecture: {platform.machine()}",
        f"CPU cores: {psutil.cpu_count(logical=False) or '?'} physical, {psutil.cpu_count()} logical",
        f"RAM: {_gb(memory.total)}",
        f"Disk: {_gb(disk.total)} total, {_gb(disk.free)} free",
        f"Uptime: {uptime}",
        f"Python: {platform.python_version()}",
        f"Agent version: {agent_version}",
    ]
    return _result(True, "\n".join(lines))


def do_resource_check() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor)
    lines = [
        f"CPU: {cpu:.0f}%",
        f"RAM: {memory.percent:.0f}% ({_gb(memory.used)} of {_gb(memory.total)})",
        f"Disk: {disk.percent:.0f}% ({_gb(disk.used)} of {_gb(disk.total)})",
    ]
    healthy = cpu < 90 and memory.percent < 90 and disk.percent < 90
    lines.append("Status: OK" if healthy else "Status: a resource is above 90%")
    return _result(healthy, "\n".join(lines))


def run_job(operation: str, parameters: dict, agent_version: str = "") -> dict:
    """Run ONE approved operation. Anything else is rejected."""
    try:
        if not isinstance(parameters, dict):
            raise BadParameter("parameters must be an object")
        if operation == "ping":
            return do_ping(check_host(parameters.get("host")))
        if operation == "dns_lookup":
            return do_dns(check_host(parameters.get("host")))
        if operation == "tcp_check":
            return do_tcp(check_host(parameters.get("host")), check_port(parameters.get("port")))
        if operation == "system_info":
            return do_system_info(agent_version)
        if operation == "resource_check":
            return do_resource_check()
        return _result(False, f"Unsupported operation: {operation}", error=True)
    except BadParameter as exc:
        return _result(False, f"Rejected parameters: {exc}", error=True)
    except Exception as exc:  # never let one job crash the agent
        log.exception("Diagnostic %s crashed", operation)
        return _result(False, f"Unexpected error while running {operation}: {type(exc).__name__}", error=True)