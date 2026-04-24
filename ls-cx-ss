#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import json
import os
import re
import shutil
import sys
import time
import stat
import urllib.request
import unicodedata
from contextlib import contextmanager
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SORT_KEYS = ("updated", "created", "provider", "branch", "session_id")
HEAD_SCAN_LINES = 12
GUTTER = 2
MIN_CONVO_WIDTH = 20
MIN_COLUMN_WIDTH = 3
KEY_ESC = 27
KEY_TAB = 9
KEY_BACKSPACE_CODES = {curses.KEY_BACKSPACE, 127, 8}
TUI_SORT_KEYS = ("updated", "created")
APP_VERSION = "0.3.3"
DEFAULT_SCRIPT_URL = "https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py"
DEFAULT_BIN_DIR = Path("~/.local/bin").expanduser()
VERSION_RE = re.compile(r'APP_VERSION = "([^"]+)"|__version__ = "([^"]+)"')
KNOWN_COMMANDS = {"list", "tui", "resume"}
HEADER_LABELS = {
    "created": "Created",
    "updated": "Updated",
    "branch": "Branch",
    "provider": "Provider",
    "session_id": "SessionID",
    "cwd": "CWD",
    "conversation": "Conversation",
}


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


@contextmanager
def attached_terminal():
    missing_fds = [fd for fd in (0, 1, 2) if not os.isatty(fd)]
    if not missing_fds:
        yield
        return

    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
    except OSError as exc:
        raise RuntimeError("This command needs an interactive terminal.") from exc

    saved_fds: dict[int, int] = {}
    try:
        for fd in missing_fds:
            saved_fds[fd] = os.dup(fd)
            os.dup2(tty_fd, fd)
        yield
    finally:
        for fd, saved_fd in saved_fds.items():
            os.dup2(saved_fd, fd)
            os.close(saved_fd)
        os.close(tty_fd)


def parse_timestamp(raw: str | datetime) -> datetime:
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def utc_from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


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


def display_slice(text: str, start: int, width: int) -> str:
    if width <= 0:
        return ""
    out: list[str] = []
    current = 0
    end = start + width
    for ch in text:
        ch_width = char_width(ch)
        next_current = current + ch_width
        if next_current <= start:
            current = next_current
            continue
        if current >= end:
            break
        out.append(ch)
        current = next_current
    return "".join(out)


def header_label(key: str, active_sort: str | None = None, reverse: bool = False) -> str:
    label = HEADER_LABELS[key]
    if key != active_sort:
        return label
    return f"{label}{' ↓' if reverse else ' ↑'}"


def base_column_widths(
    rows: Sequence[SessionRow],
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
    return fixed


def full_column_widths(
    rows: Sequence[SessionRow],
    show_cwd: bool = False,
    active_sort: str | None = None,
    reverse: bool = False,
) -> dict[str, int]:
    fixed = base_column_widths(rows, show_cwd=show_cwd, active_sort=active_sort, reverse=reverse)
    conversation_width = max(
        display_width(header_label("conversation", active_sort, reverse)),
        max((display_width(r.conversation) for r in rows), default=0),
    )
    return {**fixed, "conversation": max(MIN_CONVO_WIDTH, conversation_width)}


def table_width(widths: dict[str, int]) -> int:
    return sum(widths.values()) + GUTTER * max(0, len(widths) - 1)


def sort_rows(
    rows: Iterable[SessionRow], sort_key: str = "updated", reverse: bool | None = None
) -> list[SessionRow]:
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


def filter_rows(rows: Iterable[SessionRow], search: str) -> list[SessionRow]:
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


def compute_column_widths(
    rows: Sequence[SessionRow],
    total_width: int,
    show_cwd: bool = False,
    active_sort: str | None = None,
    reverse: bool = False,
) -> dict[str, int]:
    fixed = base_column_widths(rows, show_cwd=show_cwd, active_sort=active_sort, reverse=reverse)
    reserved = sum(fixed.values()) + (len(fixed) * GUTTER)
    if reserved + MIN_CONVO_WIDTH > total_width:
        shrink_order = ["cwd", "branch", "session_id", "provider", "updated", "created"]
        for key in shrink_order:
            while key in fixed and fixed[key] > MIN_COLUMN_WIDTH and (sum(fixed.values()) + len(fixed) * GUTTER + MIN_CONVO_WIDTH) > total_width:
                fixed[key] -= 1
    convo_width = max(1, total_width - (sum(fixed.values()) + len(fixed) * GUTTER))
    return {**fixed, "conversation": convo_width}


def format_header(
    widths: dict[str, int],
    show_cwd: bool = False,
    active_sort: str | None = None,
    reverse: bool = False,
) -> str:
    labels = [
        pad_display(header_label("created", active_sort, reverse), widths["created"]),
        pad_display(header_label("updated", active_sort, reverse), widths["updated"]),
        pad_display(header_label("branch", active_sort, reverse), widths["branch"]),
        pad_display(header_label("provider", active_sort, reverse), widths["provider"]),
        pad_display(header_label("session_id", active_sort, reverse), widths["session_id"]),
    ]
    if show_cwd:
        labels.append(pad_display(header_label("cwd", active_sort, reverse), widths["cwd"]))
    labels.append(pad_display(header_label("conversation", active_sort, reverse), widths["conversation"]))
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


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_to_local(
    url: str = DEFAULT_SCRIPT_URL,
    bin_dir: Path = DEFAULT_BIN_DIR,
    command_name: str = "ls-cx-ss",
) -> str:
    target_dir = Path(bin_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / command_name
    target_path.write_text(download_text(url), encoding="utf-8")
    ensure_executable(target_path)
    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        return f"Installed to {target_path}. Add {target_dir} to PATH if needed."
    return f"Installed to {target_path}."


def parse_version(raw: str) -> tuple[int, ...]:
    parts: list[int] = []
    for item in raw.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            break
    return tuple(parts)


def remote_version(url: str = DEFAULT_SCRIPT_URL) -> str | None:
    match = VERSION_RE.search(download_text(url))
    if not match:
        return None
    return match.group(1) or match.group(2)


def check_for_update(current_version: str = APP_VERSION, url: str = DEFAULT_SCRIPT_URL) -> str:
    latest = remote_version(url)
    if not latest:
        return "Update check failed: could not read remote version."
    if parse_version(latest) > parse_version(current_version):
        return f"Update available: {current_version} -> {latest}. Press I to install to local."
    if parse_version(latest) == parse_version(current_version):
        return f"Already up to date: {current_version}."
    return f"Running newer build: {current_version} (remote {latest})."


def init_palette() -> dict[str, int]:
    palette = {
        "title": curses.A_BOLD,
        "accent": curses.A_BOLD,
        "muted": curses.A_DIM,
        "header": curses.A_BOLD,
        "header_active": curses.A_BOLD | curses.A_UNDERLINE,
        "selected": curses.A_REVERSE | curses.A_BOLD,
        "status": curses.A_DIM,
    }
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_MAGENTA, -1)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
    except curses.error:
        return palette

    palette["title"] = curses.color_pair(1) | curses.A_BOLD
    palette["accent"] = curses.color_pair(2) | curses.A_BOLD
    palette["muted"] = curses.color_pair(3) | curses.A_DIM
    palette["header"] = curses.color_pair(3) | curses.A_BOLD
    palette["header_active"] = curses.color_pair(2) | curses.A_BOLD
    palette["selected"] = curses.A_REVERSE | curses.A_BOLD
    palette["status"] = curses.color_pair(3)
    return palette


def materialize_rows(
    rows: Sequence[SessionRow], search: str, sort_key: str, reverse: bool
) -> list[SessionRow]:
    return sort_rows(filter_rows(rows, search), sort_key=sort_key, reverse=reverse)


def resume_with_terminal(session_id: str) -> int:
    if shutil.which("codex") is None:
        raise RuntimeError("`codex` not found in PATH.")
    with attached_terminal():
        os.execvp("codex", ["codex", "resume", session_id])
    return 0


def handle_search_input(search: str, key) -> tuple[str, bool]:
    if key == "\t":
        return search, False
    if key in ("\n", "\r", "\x1b"):
        return search, False
    if key in ("\b", "\x7f"):
        return search[:-1], True
    if key == "\x15":
        return "", True
    if isinstance(key, str) and key.isprintable():
        return search + key, True
    return search, False


def sort_label(key: str, reverse: bool) -> str:
    return header_label(key, key, reverse).replace(" ↑", "").replace(" ↓", "")


def next_sort_key(current_sort: str, step: int) -> str:
    if current_sort not in TUI_SORT_KEYS:
        return TUI_SORT_KEYS[0 if step > 0 else -1]
    index = TUI_SORT_KEYS.index(current_sort)
    return TUI_SORT_KEYS[(index + step) % len(TUI_SORT_KEYS)]


def draw_header(
    stdscr,
    widths: dict[str, int],
    row_y: int,
    sort_key: str,
    reverse: bool,
    show_cwd: bool,
    width: int,
    view_x: int,
    palette: dict[str, int],
) -> None:
    fields = [
        ("created", widths["created"]),
        ("updated", widths["updated"]),
        ("branch", widths["branch"]),
        ("provider", widths["provider"]),
        ("session_id", widths["session_id"]),
    ]
    if show_cwd:
        fields.append(("cwd", widths["cwd"]))
    fields.append(("conversation", widths["conversation"]))

    x = 0
    for idx, (key, cell_width) in enumerate(fields):
        remaining = width - x
        if remaining <= 0:
            break
        label = pad_display(header_label(key, sort_key, reverse), cell_width)
        attr = palette["header"]
        if key == sort_key:
            attr = palette["header_active"]
        safe_addnstr(stdscr, row_y, x, label, remaining, attr, view_x=view_x)
        x += cell_width
        if idx != len(fields) - 1:
            remaining = width - x
            if remaining <= 0:
                break
            safe_addnstr(stdscr, row_y, x, " " * GUTTER, remaining, view_x=view_x)
            x += GUTTER


def safe_addnstr(
    stdscr,
    y: int,
    x: int,
    text: str,
    limit: int,
    attr: int = 0,
    view_x: int = 0,
) -> None:
    if limit <= 0:
        return
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y:
        return
    text_width = display_width(text)
    view_end = view_x + limit
    text_end = x + text_width
    if text_end <= view_x or x >= view_end:
        return
    visible_start = max(0, view_x - x)
    screen_x = max(0, x - view_x)
    visible_width = min(text_width - visible_start, min(limit, max_x) - screen_x)
    if visible_width <= 0 or screen_x >= max_x:
        return
    clipped = display_slice(text, visible_start, visible_width)
    if not clipped:
        return
    try:
        stdscr.addnstr(y, screen_x, clipped, min(visible_width, max_x - screen_x), attr)
    except curses.error:
        return


def draw(
    stdscr,
    all_rows: Sequence[SessionRow],
    visible_rows: Sequence[SessionRow],
    selected: int,
    scroll: int,
    search: str,
    sort_key: str,
    reverse: bool,
    show_cwd: bool,
    status: str,
    horizontal_scroll: int,
    palette: dict[str, int],
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    content_width = max(1, width - 1)
    title = "Resume a previous session"
    current_sort_label = header_label(sort_key, sort_key, reverse)
    search_label = f"Search: {search}" if search else "Type to search"
    footer = "enter resume  esc quit  tab sort  R reverse  I install to local  U check update  ↑/↓ browse  ←/→ pan"

    safe_addnstr(stdscr, 0, 0, title, content_width, palette["title"])
    sort_x = min(content_width, display_width(title) + 2)
    safe_addnstr(stdscr, 0, sort_x, "Sort: ", max(0, content_width - sort_x), palette["muted"])
    safe_addnstr(
        stdscr,
        0,
        sort_x + len("Sort: "),
        current_sort_label,
        max(0, content_width - sort_x - len("Sort: ")),
        palette["accent"],
    )
    safe_addnstr(stdscr, 1, 0, search_label, content_width, palette["muted"] if not search else palette["accent"])

    widths = full_column_widths(visible_rows or all_rows, show_cwd=show_cwd, active_sort=sort_key, reverse=reverse)
    max_horizontal_scroll = max(0, table_width(widths) - content_width)
    horizontal_scroll = min(horizontal_scroll, max_horizontal_scroll)
    header_row = 2
    draw_header(stdscr, widths, header_row, sort_key, reverse, show_cwd, content_width, horizontal_scroll, palette)

    list_top = header_row + 1
    list_height = max(1, height - list_top - 2)
    for idx, row in enumerate(visible_rows[scroll : scroll + list_height]):
        attr = palette["selected"] if scroll + idx == selected else curses.A_NORMAL
        safe_addnstr(
            stdscr,
            list_top + idx,
            0,
            format_row(row, widths, show_cwd=show_cwd),
            content_width,
            attr,
            view_x=horizontal_scroll,
        )
    if not visible_rows:
        empty = "No matching sessions." if search else "No sessions found."
        safe_addnstr(stdscr, list_top, 0, empty, content_width, palette["muted"])
    elif max_horizontal_scroll > 0:
        pan_status = f"Horizontal scroll: {horizontal_scroll}/{max_horizontal_scroll}"
        safe_addnstr(stdscr, height - 2, 0, pan_status, content_width, palette["muted"])
    if status:
        safe_addnstr(stdscr, height - 2, 0, status, content_width, palette["status"])
    safe_addnstr(stdscr, height - 1, 0, footer, content_width, palette["muted"])
    stdscr.refresh()


def run_picker(
    stdscr,
    rows: Sequence[SessionRow],
    sort_key: str = "updated",
    reverse: bool = True,
    show_cwd: bool = False,
) -> str | None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    palette = init_palette()

    selected = 0
    scroll = 0
    horizontal_scroll = 0
    search = ""
    current_sort = sort_key if sort_key in SORT_KEYS else TUI_SORT_KEYS[0]
    status = ""

    while True:
        visible_rows = materialize_rows(rows, search, current_sort, reverse)
        if selected >= len(visible_rows):
            selected = max(0, len(visible_rows) - 1)

        height, width = stdscr.getmaxyx()
        list_height = max(1, height - 5)
        if selected < scroll:
            scroll = selected
        elif selected >= scroll + list_height:
            scroll = selected - list_height + 1
        widths = full_column_widths(visible_rows or rows, show_cwd=show_cwd, active_sort=current_sort, reverse=reverse)
        max_horizontal_scroll = max(0, table_width(widths) - max(1, width - 1))
        horizontal_scroll = max(0, min(horizontal_scroll, max_horizontal_scroll))

        draw(
            stdscr,
            rows,
            visible_rows,
            selected,
            scroll,
            search,
            current_sort,
            reverse,
            show_cwd,
            status,
            horizontal_scroll,
            palette,
        )

        key = stdscr.get_wch()
        if key in ("\x1b", KEY_ESC):
            return None
        if key == curses.KEY_UP:
            selected = max(0, selected - 1)
        elif key == curses.KEY_DOWN:
            selected = min(max(0, len(visible_rows) - 1), selected + 1)
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - list_height)
        elif key == curses.KEY_NPAGE:
            selected = min(max(0, len(visible_rows) - 1), selected + list_height)
        elif key == curses.KEY_HOME:
            selected = 0
        elif key == curses.KEY_END:
            selected = max(0, len(visible_rows) - 1)
        elif key in ("\t", KEY_TAB):
            current_sort = next_sort_key(current_sort, 1)
            selected = 0
            scroll = 0
            horizontal_scroll = 0
            status = f"Sorted by {sort_label(current_sort, reverse)}."
        elif key == curses.KEY_BTAB:
            current_sort = next_sort_key(current_sort, -1)
            selected = 0
            scroll = 0
            horizontal_scroll = 0
            status = f"Sorted by {sort_label(current_sort, reverse)}."
        elif key == curses.KEY_LEFT:
            horizontal_scroll = max(0, horizontal_scroll - max(4, width // 3))
            status = ""
        elif key == curses.KEY_RIGHT:
            horizontal_scroll = min(max_horizontal_scroll, horizontal_scroll + max(4, width // 3))
            status = ""
        elif key == "R":
            reverse = not reverse
            selected = 0
            scroll = 0
            horizontal_scroll = 0
            status = f"Sort direction: {'descending' if reverse else 'ascending'}."
        elif key == "I":
            try:
                status = install_to_local()
            except Exception as exc:
                status = f"Install failed: {exc}"
        elif key == "U":
            try:
                status = check_for_update()
            except Exception as exc:
                status = f"Update check failed: {exc}"
        elif key in ("\n", "\r", curses.KEY_ENTER):
            if visible_rows:
                return visible_rows[selected].session_id
        elif key in KEY_BACKSPACE_CODES:
            search = search[:-1]
            selected = 0
            scroll = 0
            horizontal_scroll = 0
            status = ""
        else:
            search, changed = handle_search_input(search, key)
            if changed:
                selected = 0
                scroll = 0
                horizontal_scroll = 0
                status = ""


def launch_tui(
    rows: Sequence[SessionRow], sort_key: str = "updated", reverse: bool = True, show_cwd: bool = False
) -> str | None:
    if shutil.which("codex") is None:
        raise RuntimeError("`codex` not found in PATH.")
    with attached_terminal():
        return curses.wrapper(run_picker, rows, sort_key, reverse, show_cwd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ls-cx-ss",
        description="List, search, sort, and resume Codex sessions from a single self-contained Python file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--all-cwds", action="store_true", help="Show sessions across all working directories.")
    common.add_argument("--search", default="", help="Filter by conversation, session id, provider, branch, or cwd.")
    common.add_argument("--sort", choices=SORT_KEYS, default="updated", help="Sort key.")
    common.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse the default order for the selected sort key.",
    )

    list_cmd = sub.add_parser("list", parents=[common], help="Print session table.")
    list_cmd.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")

    sub.add_parser("tui", parents=[common], help="Open a TUI picker.")

    resume_cmd = sub.add_parser("resume", help="Resume a session by id.")
    resume_cmd.add_argument("session_id")

    return parser


def resolve_reverse(sort_key: str, reverse_flag: bool) -> bool:
    if reverse_flag:
        return True
    return sort_key in {"updated", "created"}


def load_materialized_rows(args) -> list[SessionRow]:
    rows = load_sessions(cwd=os.getcwd(), all_cwds=args.all_cwds)
    rows = filter_rows(rows, args.search)
    rows = sort_rows(rows, sort_key=args.sort, reverse=resolve_reverse(args.sort, args.reverse))
    return rows


def print_table(rows: list[SessionRow], show_cwd: bool) -> None:
    widths = compute_column_widths(rows, shutil.get_terminal_size((160, 24)).columns - 1, show_cwd=show_cwd)
    print(format_header(widths, show_cwd=show_cwd))
    for row in rows:
        print(format_row(row, widths, show_cwd=show_cwd))


def print_json(rows: list[SessionRow]) -> None:
    data = [
        {
            "created_at": row.created_at.isoformat(),
            "created_label": ago(row.created_at),
            "updated_at": row.updated_at.isoformat(),
            "updated_label": ago(row.updated_at),
            "branch": row.branch,
            "provider": row.provider,
            "session_id": row.session_id,
            "conversation": row.conversation,
            "cwd": row.cwd,
            "path": row.path,
        }
        for row in rows
    ]
    print(json.dumps(data, ensure_ascii=False, indent=2))


def resume_session(session_id: str) -> int:
    return resume_with_terminal(session_id)


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["tui"]
    if argv[0] == "help":
        if len(argv) == 1:
            return ["-h"]
        if argv[1] in KNOWN_COMMANDS:
            return [argv[1], "--help", *argv[2:]]
        return ["-h"]
    if argv[0] not in KNOWN_COMMANDS | {"-h", "--help"}:
        return ["tui", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "resume":
        return resume_session(args.session_id)

    rows = load_materialized_rows(args)
    show_cwd = bool(args.all_cwds)

    if args.command == "list":
        if args.json:
            print_json(rows)
        else:
            print_table(rows, show_cwd=show_cwd)
        return 0

    session_id = launch_tui(
        rows,
        sort_key=args.sort,
        reverse=resolve_reverse(args.sort, args.reverse),
        show_cwd=show_cwd,
    )
    if not session_id:
        return 0
    return resume_session(session_id)


if __name__ == "__main__":
    raise SystemExit(main())
