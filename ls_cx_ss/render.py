from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from ls_cx_ss.model import SessionRow
from ls_cx_ss.timefmt import ago

GUTTER = 2
MIN_CONVO_WIDTH = 20
MIN_COLUMN_WIDTH = 3
HEADER_LABELS = {
    "created": "Created",
    "updated": "Updated",
    "branch": "Branch",
    "provider": "Provider",
    "session_id": "SessionID",
    "cwd": "CWD",
    "conversation": "Conversation",
}


def header_label(key: str, active_sort: str | None = None, reverse: bool = False) -> str:
    label = HEADER_LABELS[key]
    if key != active_sort:
        return label
    return f"{label}{' ↓' if reverse else ' ↑'}"


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in {"W", "F"}:
        return 2
    return 1


def display_width(text: str) -> int:
    return sum(char_width(ch) for ch in text)


def truncate_display(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    if width <= 3:
        return "." * width
    target = width - 3
    out: list[str] = []
    current = 0
    for ch in text:
        w = char_width(ch)
        if current + w > target:
            break
        out.append(ch)
        current += w
    return "".join(out) + "..."


def pad_display(text: str, width: int) -> str:
    clipped = truncate_display(text, width)
    return clipped + (" " * max(0, width - display_width(clipped)))


def compute_column_widths(
    rows: Sequence[SessionRow],
    total_width: int,
    show_cwd: bool = False,
    active_sort: str | None = None,
    reverse: bool = False,
) -> dict[str, int]:
    fixed = {
        "created": max(
            display_width(header_label("created", active_sort, reverse)),
            max((display_width(ago(r.created_at)) for r in rows), default=0),
        ),
        "updated": max(
            display_width(header_label("updated", active_sort, reverse)),
            max((display_width(ago(r.updated_at)) for r in rows), default=0),
        ),
        "branch": min(
            24,
            max(
                display_width(header_label("branch", active_sort, reverse)),
                max((display_width(r.branch) for r in rows), default=0),
            ),
        ),
        "provider": min(
            16,
            max(
                display_width(header_label("provider", active_sort, reverse)),
                max((display_width(r.provider) for r in rows), default=0),
            ),
        ),
        "session_id": max(
            display_width(header_label("session_id", active_sort, reverse)),
            max((display_width(r.session_id) for r in rows), default=0),
        ),
    }
    if show_cwd:
        fixed["cwd"] = min(
            32,
            max(
                display_width(header_label("cwd", active_sort, reverse)),
                max((display_width(r.cwd) for r in rows), default=0),
            ),
        )
    reserved = sum(fixed.values()) + (len(fixed) * GUTTER)
    if reserved + 1 > total_width:
        shrink_order = ["cwd", "branch", "session_id", "provider", "updated", "created"]
        for key in shrink_order:
            while key in fixed and fixed[key] > MIN_COLUMN_WIDTH and (sum(fixed.values()) + len(fixed) * GUTTER + 1) > total_width:
                fixed[key] -= 1
    convo_width = max(1, total_width - (sum(fixed.values()) + len(fixed) * GUTTER))
    return {**fixed, "conversation": convo_width}


def format_header(widths: dict[str, int], show_cwd: bool = False) -> str:
    labels = [
        pad_display(header_label("created"), widths["created"]),
        pad_display(header_label("updated"), widths["updated"]),
        pad_display(header_label("branch"), widths["branch"]),
        pad_display(header_label("provider"), widths["provider"]),
        pad_display(header_label("session_id"), widths["session_id"]),
    ]
    if show_cwd:
        labels.append(pad_display(header_label("cwd"), widths["cwd"]))
    labels.append(pad_display(header_label("conversation"), widths["conversation"]))
    return (" " * GUTTER).join(labels)


def format_row(row: SessionRow, widths: dict[str, int], show_cwd: bool = False) -> str:
    parts = [
        pad_display(ago(row.created_at), widths["created"]),
        pad_display(ago(row.updated_at), widths["updated"]),
        pad_display(row.branch, widths["branch"]),
        pad_display(row.provider, widths["provider"]),
        pad_display(row.session_id, widths["session_id"]),
    ]
    if show_cwd:
        parts.append(pad_display(row.cwd, widths["cwd"]))
    parts.append(truncate_display(row.conversation, widths["conversation"]))
    return (" " * GUTTER).join(parts)
