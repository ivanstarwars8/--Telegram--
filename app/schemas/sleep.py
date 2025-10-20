"""Sleep schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SleepLogPayload(BaseModel):
    start_at: datetime
    end_at: datetime
