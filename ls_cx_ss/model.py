from datetime import datetime
from typing import NamedTuple

class SessionRow(NamedTuple):
    created_at: datetime
    updated_at: datetime
    branch: str
    provider: str
    session_id: str
    conversation: str
    cwd: str
    path: str
