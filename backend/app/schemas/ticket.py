from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["Network", "Hardware", "Software", "Account/access", "Other"]
Priority = Literal["Low", "Medium", "High"]


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    requester_name: str = Field(min_length=2, max_length=100)
    device_id: int | None = None
    category: Category
    priority: Priority = "Medium"
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=5000)


class TicketOut(BaseModel):
    id: int
    reference: str
    requester_name: str | None
    device_id: int | None
    device_hostname: str | None
    category: str
    priority: str
    title: str
    description: str
    status: str
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime
