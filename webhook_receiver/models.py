from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class AlertIn(BaseModel):
    timestamp: datetime
    severity: Literal["HIGH", "CRITICAL"]
    message: str
    error_count: int
    threshold: int
    window_seconds: int
    source_service: str
    ai_classification: str | None = None
    ai_root_cause: str | None = None
    ai_recommendation: str | None = None

    @field_validator("error_count", "threshold")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be > 0")
        return v


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    severity: str
    message: str
    error_count: int
    threshold: int
    window_seconds: int
    source_service: str
    ai_classification: str | None = None
    ai_root_cause: str | None = None
    ai_recommendation: str | None = None
    created_at: datetime
