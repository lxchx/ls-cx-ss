import re
import time
from datetime import datetime, timezone
from typing import Union

ISO_TZ_RE = re.compile(r"([+-]\d{2}):?(\d{2})$")


def _normalize_iso8601(raw: str) -> str:
    value = raw.strip()
    if value.endswith("Z"):
        return value[:-1] + "+0000"
    match = ISO_TZ_RE.search(value)
    if match:
        return "{0}{1}{2}".format(value[: match.start()], match.group(1), match.group(2))
    return value


def parse_timestamp(raw: Union[str, datetime]) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw

    normalized = _normalize_iso8601(raw)
    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    raise ValueError("Unsupported timestamp: {0}".format(raw))


def ago(ts: Union[str, datetime]) -> str:
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
