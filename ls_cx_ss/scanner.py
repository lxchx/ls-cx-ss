from __future__ import annotations

import json
import os
from pathlib import Path

from ls_cx_ss.model import SessionRow
from ls_cx_ss.timefmt import parse_timestamp, utc_from_timestamp

HEAD_SCAN_LINES = 12


def session_root() -> Path:
    codex_home = os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex"))
    return Path(codex_home) / "sessions"


def should_skip_message(text: str) -> bool:
    return (
        not text
        or text.startswith("# AGENTS.md instructions")
        or text.startswith("<environment_context>")
    )


def read_conversation_preview(handle) -> str:
    for _ in range(HEAD_SCAN_LINES - 1):
        line = handle.readline()
        if not line:
            break
        try:
            item = json.loads(line)
        except Exception:
            continue
        if item.get("type") != "response_item":
            continue
        payload = item.get("payload") or {}
        if payload.get("type") != "message" or payload.get("role") != "user":
            continue
        text = " ".join(
            part.get("text", "")
            for part in (payload.get("content") or ())
            if part.get("type") == "input_text"
        )
        text = " ".join(text.split()).strip()
        if should_skip_message(text):
            continue
        return text
    return "(no message yet)"


def load_sessions(cwd: str | None = None, all_cwds: bool = False) -> list[SessionRow]:
    root = session_root()
    current_cwd = os.path.realpath(cwd or os.getcwd())
    rows: list[SessionRow] = []
    if not root.exists():
        return rows

    for base, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(base, name)
            try:
                stat = os.stat(path)
                with open(path, encoding="utf-8", errors="replace") as handle:
                    first = handle.readline()
                    if not first:
                        continue
                    meta = json.loads(first)
                    if meta.get("type") != "session_meta":
                        continue
                    payload = meta.get("payload") or {}
                    session_cwd = payload.get("cwd") or ""
                    if not all_cwds and os.path.realpath(session_cwd) != current_cwd:
                        continue
                    created_raw = payload.get("timestamp") or meta.get("timestamp")
                    if not created_raw:
                        continue
                    rows.append(
                        SessionRow(
                            created_at=parse_timestamp(created_raw),
                            updated_at=utc_from_timestamp(stat.st_mtime),
                            branch=(meta.get("git") or {}).get("branch") or "-",
                            provider=payload.get("model_provider") or "-",
                            session_id=payload.get("id") or "-",
                            conversation=read_conversation_preview(handle),
                            cwd=session_cwd,
                            path=path,
                        )
                    )
            except Exception:
                continue

    return rows
