import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.devices import compute_status
from app.database import get_db
from app.models.models import Device, DiagnosticJob, DiagnosticResult, utcnow
from app.schemas.diagnostic import (
    AgentJob,
    DiagnosticJobOut,
    DiagnosticRequest,
    DiagnosticResultIn,
    DiagnosticResultOut,
)
from app.security.agent_auth import require_agent_token
from app.services.diagnostics import (
    MAX_ACTIVE_JOBS,
    MAX_SUMMARY,
    OPERATIONS,
    expire_stale_jobs,
    validate_request,
)

router = APIRouter(tags=["diagnostics"])


def job_out(db: Session, job: DiagnosticJob) -> DiagnosticJobOut:
    result = db.scalars(
        select(DiagnosticResult)
        .where(DiagnosticResult.job_id == job.id)
        .order_by(DiagnosticResult.id.desc())
    ).first()
    return DiagnosticJobOut(
        id=job.id,
        device_id=job.device_id,
        operation=job.operation,
        parameters=json.loads(job.parameters or "{}"),
        status=job.status,
        requested_at=job.requested_at,
        completed_at=job.completed_at,
        result=DiagnosticResultOut.model_validate(result) if result else None,
    )


# ---------- Admin side ----------

@router.get("/api/diagnostics/operations")
def list_operations():
    return OPERATIONS


@router.post("/api/devices/{device_id}/diagnostics", response_model=DiagnosticJobOut, status_code=201)
def create_job(device_id: int, payload: DiagnosticRequest, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if compute_status(device) != "online":
        raise HTTPException(
            status_code=409,
            detail="Device is offline. Diagnostics can only run on online devices.",
        )

    clean = validate_request(payload.operation, payload.parameters)

    expire_stale_jobs(db)
    active = db.scalar(
        select(func.count())
        .select_from(DiagnosticJob)
        .where(
            DiagnosticJob.device_id == device_id,
            DiagnosticJob.status.in_(["Pending", "Running"]),
        )
    )
    if active >= MAX_ACTIVE_JOBS:
        raise HTTPException(status_code=429, detail="Too many unfinished jobs for this device")

    job = DiagnosticJob(
        device_id=device_id,
        operation=payload.operation,
        parameters=json.dumps(clean),
        status="Pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_out(db, job)


@router.get("/api/diagnostics/{job_id}", response_model=DiagnosticJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    expire_stale_jobs(db)
    job = db.get(DiagnosticJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_out(db, job)


@router.get("/api/devices/{device_id}/diagnostics", response_model=list[DiagnosticJobOut])
def list_jobs(device_id: int, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    expire_stale_jobs(db)
    jobs = db.scalars(
        select(DiagnosticJob)
        .where(DiagnosticJob.device_id == device_id)
        .order_by(DiagnosticJob.id.desc())
        .limit(limit)
    ).all()
    return [job_out(db, j) for j in jobs]


# ---------- Agent side (token required) ----------

@router.get(
    "/api/agent/jobs",
    response_model=list[AgentJob],
    dependencies=[Depends(require_agent_token)],
)
def claim_jobs(device_id: int, db: Session = Depends(get_db)):
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    expire_stale_jobs(db)
    jobs = db.scalars(
        select(DiagnosticJob)
        .where(DiagnosticJob.device_id == device_id, DiagnosticJob.status == "Pending")
        .order_by(DiagnosticJob.id)
    ).all()
    for job in jobs:
        job.status = "Running"
    db.commit()
    return [
        AgentJob(id=j.id, operation=j.operation, parameters=json.loads(j.parameters or "{}"))
        for j in jobs
    ]


@router.post("/api/agent/jobs/{job_id}/result", dependencies=[Depends(require_agent_token)])
def submit_result(job_id: int, payload: DiagnosticResultIn, db: Session = Depends(get_db)):
    job = db.get(DiagnosticJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.device_id != payload.device_id:
        raise HTTPException(status_code=403, detail="This job belongs to another device")
    if job.status != "Running":
        raise HTTPException(status_code=409, detail="Job is not running")

    db.add(
        DiagnosticResult(
            job_id=job.id,
            result_summary=payload.summary[:MAX_SUMMARY],
            success=payload.success and not payload.error,
            duration=payload.duration,
        )
    )
    job.status = "Failed" if payload.error else "Completed"
    job.completed_at = utcnow()
    db.commit()
    return {"status": "ok"}
