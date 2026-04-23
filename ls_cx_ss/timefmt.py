from __future__ import annotations

import time
from datetime import datetime, timezone


def parse_timestamp(raw: str | datetime) -> datetime:
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def ago(ts: str | datetime) -> str:
    dt = parse_timestamp(ts)
    seconds = max(0, int(time.time() - dt.timestamp()))
    if seconds < 60:
        value, unit = seconds, "second"
    elif seconds < 3600:
        value, unit = seconds // 60, "minute"
    elif seconds < 86400:
        value, unit = seconds // 3600, "hour"
    else:
        value, unit = seconds // 86400, "day"
    suffix = "" if value == 1 else "s"
    return f"{value} {unit}{suffix} ago"


def utc_from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)
