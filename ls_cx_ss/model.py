from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime


def compat_dataclass(cls):
    if sys.version_info >= (3, 10):
        return dataclass(slots=True)(cls)
    return dataclass(cls)


@compat_dataclass
class SessionRow:
    created_at: datetime
    updated_at: datetime
    branch: str
    provider: str
    session_id: str
    conversation: str
    cwd: str
    path: str
