import json
import logging
import platform
import socket
import sys
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

import psutil
import requests

import diagnostics

AGENT_VERSION = "0.3.0"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
LOG_PATH = BASE_DIR / "agent.log"
REQUEST_TIMEOUT = 10  # seconds
RETRIES = 3
POLL_INTERVAL = 5     # seconds between checks for diagnostic jobs

log = logging.getLogger("agent")


class AuthError(Exception):
    """The server rejected the agent token."""


def setup_logging() -> None:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_agent_id() -> str:
    state = load_json(STATE_PATH)
    if "agent_id" not in state:
        state["agent_id"] = str(uuid.uuid4())
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state["agent_id"]


def get_local_ip(server_url: str) -> str | None:
    host = urlparse(server_url).hostname
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((host, 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def collect_metrics() -> dict:
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage(Path.home().anchor).percent,
    }


def post_json(config: dict, path: str, payload: dict):
    """POST with timeout and retries. Returns the response, or None if the
    server stayed unreachable. Raises AuthError on 401/403."""
    url = f"{config['server_url']}{path}"
    headers = {"X-Agent-Token": config.get("agent_token", "")}
    delay = 2
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            log.warning("Attempt %d/%d to %s failed: %s", attempt, RETRIES, path, exc)
        else:
            if resp.status_code in (401, 403):
                raise AuthError(f"Server rejected the agent token ({resp.status_code})")
            if resp.status_code < 500:
                return resp
            log.warning(
                "Attempt %d/%d to %s: server error %d",
                attempt, RETRIES, path, resp.status_code,
            )
        if attempt < RETRIES:
            time.sleep(delay)
            delay *= 2  # 2s, 4s, ...
    return None


def fetch_jobs(config: dict, device_id: int):
    """Ask the server for pending diagnostic jobs.
    Returns a list (empty on a temporary problem), or None if the server
    does not know this device any more."""
    headers = {"X-Agent-Token": config.get("agent_token", "")}
    try:
        resp = requests.get(
            f"{config['server_url']}/api/agent/jobs",
            params={"device_id": device_id},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except (requests.ConnectionError, requests.Timeout):
        return []  # the heartbeat already reports connection problems
    if resp.status_code in (401, 403):
        raise AuthError(f"Server rejected the agent token ({resp.status_code})")
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        log.warning("Job poll refused (%d)", resp.status_code)
        return []
    return resp.json()


def handle_job(config: dict, device_id: int, job: dict) -> None:
    log.info("Running diagnostic job %s (%s)", job["id"], job["operation"])
    started = time.monotonic()
    result = diagnostics.run_job(job["operation"], job["parameters"], AGENT_VERSION)
    payload = {
        "device_id": device_id,
        "success": result["success"],
        "summary": result["summary"],
        "duration": round(time.monotonic() - started, 2),
        "error": result["error"],
    }
    resp = post_json(config, f"/api/agent/jobs/{job['id']}/result", payload)
    if resp is None:
        log.warning("Could not send the result of job %s", job["id"])
    elif resp.status_code == 200:
        log.info("Result of job %s sent", job["id"])
    else:
        log.error("Result of job %s refused (%d): %s", job["id"], resp.status_code, resp.text)


def register(config: dict, agent_id: str) -> int | None:
    payload = {
        "agent_id": agent_id,
        "hostname": socket.gethostname(),
        "ip_address": get_local_ip(config["server_url"]),
        "os": f"{platform.system()} {platform.release()}",
        "device_type": config.get("device_type", "pc"),
        "is_simulated": False,
        "department": config.get("department"),
        "owner": config.get("owner"),
        "agent_version": AGENT_VERSION,
    }
    resp = post_json(config, "/api/devices/register", payload)
    if resp is None:
        return None
    if resp.status_code != 200:
        log.error("Registration refused (%d): %s", resp.status_code, resp.text)
        return None
    return resp.json()["id"]


def run() -> None:
    config = load_json(CONFIG_PATH)
    if not config.get("server_url"):
        sys.exit("config.json is missing or has no server_url")
    if not config.get("agent_token"):
        sys.exit("config.json has no agent_token")

    agent_id = get_agent_id()
    interval = config.get("heartbeat_interval", 60)
    log.info("Agent %s starting (version %s)", agent_id, AGENT_VERSION)

    device_id = None
    last_heartbeat = 0.0
    while True:
        if device_id is None:
            device_id = register(config, agent_id)
            if device_id is None:
                log.warning("Registration failed, retrying in 30s")
                time.sleep(30)
                continue
            log.info("Registered as device %d", device_id)
            last_heartbeat = 0.0  # send a heartbeat right away

        if time.monotonic() - last_heartbeat >= interval:
            payload = {
                "device_id": device_id,
                "ip_address": get_local_ip(config["server_url"]),
                **collect_metrics(),
            }
            resp = post_json(config, "/api/devices/heartbeat", payload)
            if resp is None:
                log.warning("Server unreachable, will try again next cycle")
            elif resp.status_code == 200:
                log.info("Heartbeat sent")
            elif resp.status_code == 404:
                log.warning("Server does not know this device, re-registering")
                device_id = None
                continue
            else:
                log.error("Heartbeat refused (%d): %s", resp.status_code, resp.text)
            last_heartbeat = time.monotonic()

        jobs = fetch_jobs(config, device_id)
        if jobs is None:
            log.warning("Server does not know this device, re-registering")
            device_id = None
            continue
        for job in jobs:
            handle_job(config, device_id, job)

        time.sleep(POLL_INTERVAL)


def main() -> None:
    setup_logging()
    try:
        run()
    except AuthError as exc:
        log.critical("%s. Check agent_token in config.json.", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Agent stopped by user")


if __name__ == "__main__":
    main()