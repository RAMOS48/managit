from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticRequest(BaseModel):
    operation: str = Field(min_length=1, max_length=50)
    parameters: dict[str, str | int] = Field(default_factory=dict)


class DiagnosticResultIn(BaseModel):
    """Sent by the agent when a job is finished."""
    device_id: int
    success: bool                 # outcome of the check (for example host reachable)
    summary: str = Field(max_length=20000)
    duration: float | None = Field(default=None, ge=0)
    error: bool = False           # True = the job could not run at all


class DiagnosticResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    result_summary: str
    duration: float | None
    created_at: datetime


class DiagnosticJobOut(BaseModel):
    id: int
    device_id: int
    operation: str
    parameters: dict
    status: str
    requested_at: datetime
    completed_at: datetime | None
    result: DiagnosticResultOut | None = None


class AgentJob(BaseModel):
    id: int
    operation: str
    parameters: dict
