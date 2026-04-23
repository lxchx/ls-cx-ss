from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from ls_cx_ss.model import SessionRow
from ls_cx_ss.timefmt import ago

GUTTER = 2
MIN_CONVO_WIDTH = 20


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
    rows: Sequence[SessionRow], total_width: int, show_cwd: bool = False
) -> dict[str, int]:
    fixed = {
        "created": max(len("Created"), max((display_width(ago(r.created_at)) for r in rows), default=0)),
        "updated": max(len("Updated"), max((display_width(ago(r.updated_at)) for r in rows), default=0)),
        "branch": min(24, max(len("Branch"), max((display_width(r.branch) for r in rows), default=0))),
        "provider": min(16, max(len("Provider"), max((display_width(r.provider) for r in rows), default=0))),
        "session_id": max(len("SessionID"), max((display_width(r.session_id) for r in rows), default=0)),
    }
    if show_cwd:
        fixed["cwd"] = min(32, max(len("CWD"), max((display_width(r.cwd) for r in rows), default=0)))
    reserved = sum(fixed.values()) + (len(fixed) * GUTTER)
    convo_width = max(MIN_CONVO_WIDTH, total_width - reserved - 1)
    return {**fixed, "conversation": convo_width}


def format_header(widths: dict[str, int], show_cwd: bool = False) -> str:
    labels = [
        pad_display("Created", widths["created"]),
        pad_display("Updated", widths["updated"]),
        pad_display("Branch", widths["branch"]),
        pad_display("Provider", widths["provider"]),
        pad_display("SessionID", widths["session_id"]),
    ]
    if show_cwd:
        labels.append(pad_display("CWD", widths["cwd"]))
    labels.append(pad_display("Conversation", widths["conversation"]))
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
