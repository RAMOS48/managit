from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.devices import compute_status
from app.database import get_db
from app.models.models import Device, MetricSnapshot
from app.schemas.device import MetricOut

router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/monitoring/summary")
def summary(db: Session = Depends(get_db)):
    devices = db.scalars(select(Device)).all()
    online = sum(1 for d in devices if compute_status(d) == "online")
    return {
        "total": len(devices),
        "online": online,
        "offline": len(devices) - online,
        "simulated": sum(1 for d in devices if d.is_simulated),
        "real": sum(1 for d in devices if not d.is_simulated),
    }


@router.get("/devices/{device_id}/metrics", response_model=list[MetricOut])
def device_metrics(
    device_id: int,
    limit: int = Query(default=60, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    stmt = (
        select(MetricSnapshot)
        .where(MetricSnapshot.device_id == device_id)
        .order_by(MetricSnapshot.collected_at.desc(), MetricSnapshot.id.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()
