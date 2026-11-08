from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Device, Ticket
from app.schemas.ticket import (
    Category,
    Priority,
    Status,
    TicketCreate,
    TicketOut,
    TicketUpdate,
)

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


# ---------- Admin side ----------

@router.get("/api/ticket-options")
def ticket_options():
    return {
        "statuses": list(get_args(Status)),
        "categories": list(get_args(Category)),
        "priorities": list(get_args(Priority)),
    }


@router.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(
    status: Status | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    return [ticket_out(db, t) for t in db.scalars(stmt).all()]


@router.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket_out(db, ticket)


@router.patch("/api/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to update")

    new_status = ticket.status
    if "status" in changes:
        if changes["status"] is None:
            raise HTTPException(status_code=422, detail="Status cannot be empty")
        new_status = changes["status"]

    new_note = ticket.resolution_note
    if "resolution_note" in changes:
        new_note = changes["resolution_note"] or None

    new_device = ticket.device_id
    if "device_id" in changes:
        new_device = changes["device_id"]
        if new_device is not None and db.get(Device, new_device) is None:
            raise HTTPException(status_code=404, detail="Device not found")

    if new_status == "Resolved" and not new_note:
        raise HTTPException(
            status_code=422,
            detail="A resolution note is required to resolve a ticket",
        )

    ticket.status = new_status
    ticket.resolution_note = new_note
    ticket.device_id = new_device
    db.commit()
    db.refresh(ticket)
    return ticket_out(db, ticket)
