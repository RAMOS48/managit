import json
import random
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
HEARTBEAT_INTERVAL = 30   # seconds between heartbeats of each device
POLL_INTERVAL = 5         # seconds between checks for diagnostic jobs
TIMEOUT = 10              # request timeout in seconds
OPEN_PORTS = {22, 80, 443, 445, 3389, 8000}   # ports that "answer" in the simulation

# stop_after = seconds after start when the device stops sending heartbeats
# (None = never stops, 0 = registers once and never sends a heartbeat)
FLEET = [
    {"agent_id": "sim-001", "hostname": "PC-HR-01", "os": "Windows 10", "device_type": "pc",
     "department": "HR", "owner": "Amina B.", "ip_address": "192.168.56.101", "stop_after": None},
    {"agent_id": "sim-002", "hostname": "PC-FIN-01", "os": "Windows 11", "device_type": "pc",
     "department": "Finance", "owner": "Karim L.", "ip_address": "192.168.56.102", "stop_after": None},
    {"agent_id": "sim-003", "hostname": "LAPTOP-SALES-01", "os": "Windows 11", "device_type": "laptop",
     "department": "Sales", "owner": "Sara M.", "ip_address": "192.168.56.103", "stop_after": None},
    {"agent_id": "sim-004", "hostname": "SRV-FILES-01", "os": "Ubuntu 22.04", "device_type": "server",
     "department": "IT", "owner": "IT Team", "ip_address": "192.168.56.104", "stop_after": None},
    {"agent_id": "sim-005", "hostname": "LAPTOP-MKT-01", "os": "Windows 10", "device_type": "laptop",
     "department": "Marketing", "owner": "Yacine D.", "ip_address": "192.168.56.105", "stop_after": 120},
    {"agent_id": "sim-006", "hostname": "PC-ACC-01", "os": "Windows 10", "device_type": "pc",
     "department": "Accounting", "owner": "Nadia R.", "ip_address": "192.168.56.106", "stop_after": 120},
    {"agent_id": "sim-007", "hostname": "SRV-BACKUP-01", "os": "Debian 12", "device_type": "server",
     "department": "IT", "owner": "IT Team", "ip_address": "192.168.56.107", "stop_after": 240},
    {"agent_id": "sim-008", "hostname": "PC-OLD-01", "os": "Windows 7", "device_type": "pc",
     "department": "Archive", "owner": "Unassigned", "ip_address": "192.168.56.108", "stop_after": 0},
]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit("config.json not found. Run from the project root.")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("server_url") or not config.get("agent_token"):
        sys.exit("config.json needs server_url and agent_token")
    return config


def clamp(value: float) -> float:
    return max(1.0, min(99.0, value))


def drift(value: float, step: float) -> float:
    """Small random walk so the values look realistic."""
    return clamp(value + random.uniform(-step, step))


def is_active(dev: dict, elapsed: float) -> bool:
    stop = dev["stop_after"]
    return stop is None or elapsed < stop


# ---------- Fake diagnostics (clearly labelled as simulated) ----------

def fake_result(dev: dict, operation: str, params: dict) -> dict:
    tag = "[SIMULATED] "
    if operation == "ping":
        host = str(params.get("host", "?"))
        times = [random.randint(1, 25) for _ in range(4)]
        lines = [f"Reply from {host}: time={t}ms TTL=64" for t in times]
        summary = (f"{tag}{host} is reachable\n\n" + "\n".join(lines) +
                   f"\n\nAverage = {sum(times) // len(times)}ms")
        return {"success": True, "summary": summary, "error": False}

    if operation == "dns_lookup":
        host = str(params.get("host", "?"))
        # 203.0.113.0/24 is reserved for documentation, so it is clearly fake
        address = f"203.0.113.{sum(host.encode()) % 254 + 1}"
        return {"success": True, "summary": f"{tag}{host} resolves to:\n{address}", "error": False}

    if operation == "tcp_check":
        host, port = str(params.get("host", "?")), params.get("port")
        if port in OPEN_PORTS:
            summary = f"{tag}{host}:{port} is open (connected in {random.randint(2, 40)} ms)"
            return {"success": True, "summary": summary, "error": False}
        return {"success": False, "summary": f"{tag}{host}:{port} is closed or unreachable", "error": False}

    if operation == "system_info":
        summary = "\n".join([
            f"{tag}Hostname: {dev['name']}",
            f"Operating system: {dev['os']}",
            f"IP address: {dev['ip']}",
            f"Department: {dev['department']}",
            f"Owner: {dev['owner']}",
            "Agent version: sim-0.2",
        ])
        return {"success": True, "summary": summary, "error": False}

    if operation == "resource_check":
        healthy = dev["cpu"] < 90 and dev["mem"] < 90 and dev["disk"] < 90
        summary = "\n".join([
            f"{tag}CPU: {dev['cpu']:.0f}%",
            f"RAM: {dev['mem']:.0f}%",
            f"Disk: {dev['disk']:.0f}%",
            "Status: OK" if healthy else "Status: a resource is above 90%",
        ])
        return {"success": healthy, "summary": summary, "error": False}

    return {"success": False, "summary": f"{tag}Unsupported operation: {operation}", "error": True}


def main() -> None:
    config = load_config()
    base = config["server_url"]
    headers = {"X-Agent-Token": config["agent_token"]}
    session = requests.Session()

    devices = []
    for spec in FLEET:
        payload = {
            "agent_id": spec["agent_id"],
            "hostname": spec["hostname"],
            "ip_address": spec["ip_address"],
            "os": spec["os"],
            "device_type": spec["device_type"],
            "is_simulated": True,
            "department": spec["department"],
            "owner": spec["owner"],
            "agent_version": "sim-0.2",
        }
        try:
            resp = session.post(f"{base}/api/devices/register", json=payload,
                                headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            sys.exit(f"Cannot reach the server: {exc}")
        if resp.status_code in (401, 403):
            sys.exit("The server rejected the agent token. Check config.json.")
        resp.raise_for_status()
        devices.append({
            "id": resp.json()["id"],
            "name": spec["hostname"],
            "os": spec["os"],
            "ip": spec["ip_address"],
            "department": spec["department"],
            "owner": spec["owner"],
            "stop_after": spec["stop_after"],
            "cpu": random.uniform(10, 60),
            "mem": random.uniform(30, 80),
            "disk": random.uniform(30, 75),
            "last_heartbeat": 0.0,
        })
        print(f"Registered {spec['hostname']} as device {resp.json()['id']}")

    start = time.time()
    print(f"\nSimulating {len(devices)} devices (Ctrl+C to stop)\n")
    try:
        while True:
            now = time.time()
            elapsed = now - start
            sent = 0
            for dev in devices:
                if not is_active(dev, elapsed):
                    continue  # this device has "gone offline"

                # 1) Heartbeat, every HEARTBEAT_INTERVAL seconds
                if now - dev["last_heartbeat"] >= HEARTBEAT_INTERVAL:
                    dev["cpu"] = drift(dev["cpu"], 15)
                    dev["mem"] = drift(dev["mem"], 5)
                    dev["disk"] = drift(dev["disk"], 0.2)
                    payload = {
                        "device_id": dev["id"],
                        "ip_address": dev["ip"],
                        "cpu_percent": round(dev["cpu"], 1),
                        "memory_percent": round(dev["mem"], 1),
                        "disk_percent": round(dev["disk"], 1),
                    }
                    try:
                        resp = session.post(f"{base}/api/devices/heartbeat", json=payload,
                                            headers=headers, timeout=TIMEOUT)
                        if resp.status_code == 200:
                            sent += 1
                        else:
                            print(f"{dev['name']}: heartbeat refused ({resp.status_code})")
                    except requests.RequestException as exc:
                        print(f"{dev['name']}: server unreachable ({exc})")
                    dev["last_heartbeat"] = now

                # 2) Diagnostic jobs, every POLL_INTERVAL seconds
                try:
                    resp = session.get(f"{base}/api/agent/jobs", params={"device_id": dev["id"]},
                                       headers=headers, timeout=TIMEOUT)
                    jobs = resp.json() if resp.status_code == 200 else []
                except requests.RequestException:
                    jobs = []
                for job in jobs:
                    result = fake_result(dev, job["operation"], job["parameters"])
                    result_payload = {
                        "device_id": dev["id"],
                        "success": result["success"],
                        "summary": result["summary"],
                        "duration": round(random.uniform(0.3, 2.5), 2),
                        "error": result["error"],
                    }
                    try:
                        session.post(f"{base}/api/agent/jobs/{job['id']}/result",
                                     json=result_payload, headers=headers, timeout=TIMEOUT)
                        print(f"{dev['name']}: answered job {job['id']} ({job['operation']})")
                    except requests.RequestException as exc:
                        print(f"{dev['name']}: could not send result ({exc})")

            if sent:
                active = sum(1 for d in devices if is_active(d, elapsed))
                print(f"{time.strftime('%H:%M:%S')} heartbeats sent, {active} devices active")
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nSimulator stopped")


if __name__ == "__main__":
    main()