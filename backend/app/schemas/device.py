from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DeviceRegister(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    hostname: str = Field(min_length=1, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    os: str | None = Field(default=None, max_length=100)
    device_type: str = Field(default="pc", max_length=30)
    is_simulated: bool = False
    department: str | None = Field(default=None, max_length=100)
    owner: str | None = Field(default=None, max_length=100)
    agent_version: str | None = Field(default=None, max_length=20)


class HeartbeatIn(BaseModel):
    device_id: int
    ip_address: str | None = Field(default=None, max_length=45)
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cpu_percent: float
    memory_percent: float
    disk_percent: float
    collected_at: datetime


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    agent_id: str | None
    ip_address: str | None
    os: str | None
    device_type: str
    is_simulated: bool
    department: str | None
    owner: str | None
    agent_version: str | None
    created_at: datetime
    last_seen: datetime | None
    status: str = "offline"
    latest_metrics: MetricOut | None = None
