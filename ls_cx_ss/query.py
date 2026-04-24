from typing import Iterable, List, Optional

from ls_cx_ss.model import SessionRow

SORT_KEYS = ("updated", "created", "provider", "branch", "session_id")


def sort_rows(
    rows: Iterable[SessionRow], sort_key: str = "updated", reverse: Optional[bool] = None
) -> List[SessionRow]:
    items = list(rows)
    key = sort_key if sort_key in SORT_KEYS else "updated"

    if reverse is None:
        reverse = key in {"updated", "created"}

    if key == "updated":
        return sorted(items, key=lambda row: row.updated_at, reverse=reverse)
    if key == "created":
        return sorted(items, key=lambda row: row.created_at, reverse=reverse)
    if key == "provider":
        return sorted(items, key=lambda row: (row.provider.casefold(), row.updated_at), reverse=reverse)
    if key == "branch":
        return sorted(items, key=lambda row: (row.branch.casefold(), row.updated_at), reverse=reverse)
    return sorted(items, key=lambda row: (row.session_id.casefold(), row.updated_at), reverse=reverse)


def filter_rows(rows: Iterable[SessionRow], search: str) -> List[SessionRow]:
    term = search.strip().casefold()
    if not term:
        return list(rows)
    return [
        row
        for row in rows
        if term in row.conversation.casefold()
        or term in row.session_id.casefold()
        or term in row.provider.casefold()
        or term in row.branch.casefold()
        or term in row.cwd.casefold()
    ]
