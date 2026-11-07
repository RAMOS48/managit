import ipaddress
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import DiagnosticJob, DiagnosticResult, utcnow

JOB_TIMEOUT = timedelta(minutes=5)
MAX_SUMMARY = 4000
MAX_ACTIVE_JOBS = 5

# Must start and end with a letter or digit, so a value can never start with "-"
HOSTNAME_RE = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")

# The ONLY operations that can ever run. Anything else is rejected.
OPERATIONS = {
    "ping": {"label": "Ping a host", "params": ["host"]},
    "dns_lookup": {"label": "DNS lookup", "params": ["host"]},
    "tcp_check": {"label": "TCP port check", "params": ["host", "port"]},
    "system_info": {"label": "System information", "params": []},
    "resource_check": {"label": "CPU, RAM and disk usage", "params": []},
}


def _validate_host(value) -> str:
    if not isinstance(value, str):
        raise HTTPException(422, "Parameter 'host' must be text")
    host = value.strip()
    if not host or len(host) > 253:
        raise HTTPException(422, "Parameter 'host' is empty or too long")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if not HOSTNAME_RE.fullmatch(host):
        raise HTTPException(422, "Parameter 'host' must be a valid hostname or IP address")
    return host


def _validate_port(value) -> int:
    if isinstance(value, bool):
        raise HTTPException(422, "Parameter 'port' must be a number")
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not 1 <= value <= 65535:
        raise HTTPException(422, "Parameter 'port' must be a number between 1 and 65535")
    return value


def validate_request(operation: str, parameters: dict) -> dict:
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise HTTPException(422, "Unsupported operation. Allowed: " + ", ".join(OPERATIONS))

    unknown = set(parameters) - set(spec["params"])
    if unknown:
        raise HTTPException(422, "Unexpected parameter(s): " + ", ".join(sorted(unknown)))
    missing = [p for p in spec["params"] if p not in parameters]
    if missing:
        raise HTTPException(422, "Missing parameter(s): " + ", ".join(missing))

    clean: dict = {}
    if "host" in spec["params"]:
        clean["host"] = _validate_host(parameters["host"])
    if "port" in spec["params"]:
        clean["port"] = _validate_port(parameters["port"])
    return clean


def expire_stale_jobs(db: Session) -> None:
    """Fail jobs that were never picked up, or never finished, within JOB_TIMEOUT."""
    cutoff = utcnow() - JOB_TIMEOUT
    stale = db.scalars(
        select(DiagnosticJob).where(
            DiagnosticJob.status.in_(["Pending", "Running"]),
            DiagnosticJob.requested_at < cutoff,
        )
    ).all()
    if not stale:
        return
    now = utcnow()
    for job in stale:
        reason = (
            "The device did not pick up the job in time."
            if job.status == "Pending"
            else "The device did not report a result in time."
        )
        job.status = "Failed"
        job.completed_at = now
        db.add(DiagnosticResult(job_id=job.id, result_summary=reason, success=False))
    db.commit()
