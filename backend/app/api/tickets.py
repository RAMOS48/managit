from typing import get_args

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Device, Ticket
from app.schemas.ticket import Category, Priority, TicketCreate, TicketOut

router = APIRouter(tags=["tickets"])


def ticket_ref(ticket_id: int) -> str:
    return f"TCK-{ticket_id:04d}"


def ticket_out(db: Session, ticket: Ticket) -> TicketOut:
    device = db.get(Device, ticket.device_id) if ticket.device_id else None
    return TicketOut(
        id=ticket.id,
        reference=ticket_ref(ticket.id),
        requester_name=ticket.requester_name,
        device_id=ticket.device_id,
        device_hostname=device.hostname if device else None,
        category=ticket.category,
        priority=ticket.priority,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        resolution_note=ticket.resolution_note,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


# ---------- Employee portal helpers (kept minimal on purpose) ----------

@router.get("/api/portal/options")
def portal_options():
    return {
        "categories": list(get_args(Category)),
        "priorities": list(get_args(Priority)),
    }


@router.get("/api/portal/devices")
def portal_devices(db: Session = Depends(get_db)):
    rows = db.execute(select(Device.id, Device.hostname).order_by(Device.hostname)).all()
    return [{"id": r.id, "hostname": r.hostname} for r in rows]


# ---------- Tickets ----------

@router.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    if payload.device_id is not None and db.get(Device, payload.device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")

    ticket = Ticket(
        requester_name=payload.requester_name,
        device_id=payload.device_id,
        category=payload.category,
        priority=payload.priority,
        title=payload.title,
        description=payload.description,
        status="Open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket_out(db, ticket)
