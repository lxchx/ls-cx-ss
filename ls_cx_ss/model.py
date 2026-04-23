from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SessionRow:
    created_at: datetime
    updated_at: datetime
    branch: str
    provider: str
    session_id: str
    conversation: str
    cwd: str
    path: str
