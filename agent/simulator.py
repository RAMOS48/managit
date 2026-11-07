import json
import random
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
INTERVAL = 30          # seconds between heartbeat rounds
TIMEOUT = 10           # request timeout in seconds

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
            "agent_version": "sim-0.1",
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
            "ip": spec["ip_address"],
            "stop_after": spec["stop_after"],
            "cpu": random.uniform(10, 60),
            "mem": random.uniform(30, 80),
            "disk": random.uniform(30, 75),
        })
        print(f"Registered {spec['hostname']} as device {resp.json()['id']}")

    start = time.time()
    print(f"\nSimulating {len(devices)} devices (Ctrl+C to stop)\n")
    try:
        while True:
            elapsed = time.time() - start
            for dev in devices:
                stop = dev["stop_after"]
                if stop is not None and elapsed >= stop:
                    continue  # this device has "gone offline"
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
                    if resp.status_code != 200:
                        print(f"{dev['name']}: heartbeat refused ({resp.status_code})")
                except requests.RequestException as exc:
                    print(f"{dev['name']}: server unreachable ({exc})")
            active = sum(1 for d in devices
                         if d["stop_after"] is None or elapsed < d["stop_after"])
            print(f"{time.strftime('%H:%M:%S')} round done, {active} devices sending")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nSimulator stopped")


if __name__ == "__main__":
    main()