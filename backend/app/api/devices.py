from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.agent_auth import require_agent_token
from app.security.auth import require_admin
from app.models.models import Device, MetricSnapshot, utcnow
from app.schemas.device import DeviceRegister, HeartbeatIn, DeviceOut, MetricOut

router = APIRouter(prefix="/api/devices", tags=["devices"])

OFFLINE_AFTER_SECONDS = 90


def compute_status(device: Device) -> str:
    if device.last_seen is None:
        return "offline"
    if utcnow() - device.last_seen > timedelta(seconds=OFFLINE_AFTER_SECONDS):
        return "offline"
    return "online"


def latest_metric(db: Session, device_id: int) -> MetricSnapshot | None:
    stmt = (
        select(MetricSnapshot)
        .where(MetricSnapshot.device_id == device_id)
        .order_by(MetricSnapshot.collected_at.desc(), MetricSnapshot.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def to_out(db: Session, device: Device) -> DeviceOut:
    out = DeviceOut.model_validate(device)
    out.status = compute_status(device)
    metric = latest_metric(db, device.id)
    out.latest_metrics = MetricOut.model_validate(metric) if metric else None
    return out


@router.post("/register", response_model=DeviceOut, dependencies=[Depends(require_agent_token)])
def register_device(payload: DeviceRegister, db: Session = Depends(get_db)):
    # Same agent_id registering again (agent restart) updates the existing device
    device = db.scalars(
        select(Device).where(Device.agent_id == payload.agent_id)
    ).first()

    if device is None:
        device = Device(**payload.model_dump())
        db.add(device)
    else:
        for field, value in payload.model_dump().items():
            setattr(device, field, value)

    device.last_seen = utcnow()
    db.commit()
    db.refresh(device)
    return to_out(db, device)


@router.post("/heartbeat", dependencies=[Depends(require_agent_token)])
def heartbeat(payload: HeartbeatIn, db: Session = Depends(get_db)):
    device = db.get(Device, payload.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    now = utcnow()
    device.last_seen = now
    if payload.ip_address:
        device.ip_address = payload.ip_address

    db.add(
        MetricSnapshot(
            device_id=device.id,
            cpu_percent=payload.cpu_percent,
            memory_percent=payload.memory_percent,
            disk_percent=payload.disk_percent,
            collected_at=now,
        )
    )
    db.commit()
    return {"status": "ok", "device_id": device.id, "last_seen": now}


@router.get("", response_model=list[DeviceOut], dependencies=[Depends(require_admin)])
def list_devices(db: Session = Depends(get_db)):
    devices = db.scalars(select(Device).order_by(Device.id)).all()
    return [to_out(db, d) for d in devices]


@router.get("/{device_id}", response_model=DeviceOut, dependencies=[Depends(require_admin)])
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return to_out(db, device)
