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
APP_VERSION = "0.2.0"
DEFAULT_SCRIPT_URL = "https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py"
DEFAULT_BIN_DIR = Path("~/.local/bin").expanduser()
VERSION_RE = re.compile(r'APP_VERSION = "([^"]+)"|__version__ = "([^"]+)"')
HEADER_LABELS = {
    "created": "Created",
    "updated": "Updated",
    "branch": "Branch",
    "provider": "Provider",
    "session_id": "SessionID",
    "cwd": "CWD",
    "conversation": "Conversation",
}


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


@contextmanager
def attached_terminal():
    if os.isatty(0) and os.isatty(1):
        yield
        return

    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
    except OSError as exc:
        raise RuntimeError("This command needs an interactive terminal.") from exc

    saved_stdin = os.dup(0)
    saved_stdout = os.dup(1)
    saved_stderr = os.dup(2)
    try:
        os.dup2(tty_fd, 0)
        os.dup2(tty_fd, 1)
        os.dup2(tty_fd, 2)
        yield
    finally:
        os.dup2(saved_stdin, 0)
        os.dup2(saved_stdout, 1)
        os.dup2(saved_stderr, 2)
        os.close(saved_stdin)
        os.close(saved_stdout)
        os.close(saved_stderr)
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


def header_label(key: str, active_sort: str | None = None, reverse: bool = False) -> str:
    label = HEADER_LABELS[key]
    if key != active_sort:
        return label
    return f"{label}{' ↓' if reverse else ' ↑'}"


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
        return f"Update available: {current_version} -> {latest}. Press i to install."
    if parse_version(latest) == parse_version(current_version):
        return f"Already up to date: {current_version}."
    return f"Running newer build: {current_version} (remote {latest})."


def prompt_input(stdscr, label: str, initial: str = "") -> str:
    height, width = stdscr.getmaxyx()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    curses.echo()
    try:
        stdscr.move(height - 1, 0)
        stdscr.clrtoeol()
        prompt = f"{label}{initial}"
        stdscr.addnstr(height - 1, 0, prompt, width - 1)
        stdscr.refresh()
        typed = stdscr.getstr(height - 1, len(label), max(1, width - len(label) - 1))
        return typed.decode("utf-8", errors="replace")
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass


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


def draw_header(
    stdscr,
    widths: dict[str, int],
    row_y: int,
    sort_key: str,
    reverse: bool,
    show_cwd: bool,
    width: int,
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
        attr = curses.A_BOLD
        if key == sort_key:
            attr |= curses.A_REVERSE
        safe_addnstr(stdscr, row_y, x, label, remaining, attr)
        x += cell_width
        if idx != len(fields) - 1:
            remaining = width - x
            if remaining <= 0:
                break
            safe_addnstr(stdscr, row_y, x, " " * GUTTER, remaining)
            x += GUTTER


def safe_addnstr(stdscr, y: int, x: int, text: str, limit: int, attr: int = 0) -> None:
    if limit <= 0:
        return
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    clipped = truncate_display(text, min(limit, max_x - x))
    if not clipped:
        return
    try:
        stdscr.addnstr(y, x, clipped, min(limit, max_x - x), attr)
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
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    title = f"ls-cx-ss v{APP_VERSION}  cwd={os.getcwd()}  rows={len(visible_rows)}/{len(all_rows)}"
    hint = f"/ search  s sort  r reverse  i install  u update  Enter resume  q/Esc quit"
    safe_addnstr(stdscr, 0, 0, title, width - 1, curses.A_BOLD)
    meta_row = 1
    if status:
        safe_addnstr(stdscr, meta_row, 0, status, width - 1)
        meta_row += 1
    if search:
        safe_addnstr(stdscr, meta_row, 0, f"search: {search}", width - 1)
        meta_row += 1

    widths = compute_column_widths(
        visible_rows or all_rows,
        width - 1,
        show_cwd=show_cwd,
        active_sort=sort_key,
        reverse=reverse,
    )
    draw_header(stdscr, widths, meta_row, sort_key, reverse, show_cwd, width - 1)

    list_top = meta_row + 1
    list_height = max(1, height - list_top - 1)
    for idx, row in enumerate(visible_rows[scroll : scroll + list_height]):
        attr = curses.A_REVERSE if scroll + idx == selected else curses.A_NORMAL
        safe_addnstr(stdscr, list_top + idx, 0, format_row(row, widths, show_cwd=show_cwd), width - 1, attr)
    safe_addnstr(stdscr, height - 1, 0, hint, width - 1)
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

    selected = 0
    scroll = 0
    search = ""
    sort_index = SORT_KEYS.index(sort_key) if sort_key in SORT_KEYS else 0
    status = "Ready. Enter resumes the selected session."

    while True:
        current_sort = SORT_KEYS[sort_index]
        visible_rows = materialize_rows(rows, search, current_sort, reverse)
        if selected >= len(visible_rows):
            selected = max(0, len(visible_rows) - 1)

        height, _ = stdscr.getmaxyx()
        meta_rows = 2 + (1 if status else 0) + (1 if search else 0)
        list_height = max(1, height - meta_rows - 1)
        if selected < scroll:
            scroll = selected
        elif selected >= scroll + list_height:
            scroll = selected - list_height + 1

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
        )

        key = stdscr.getch()
        if key in (ord("q"), KEY_ESC):
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(max(0, len(visible_rows) - 1), selected + 1)
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - list_height)
        elif key == curses.KEY_NPAGE:
            selected = min(max(0, len(visible_rows) - 1), selected + list_height)
        elif key == curses.KEY_HOME:
            selected = 0
        elif key == curses.KEY_END:
            selected = max(0, len(visible_rows) - 1)
        elif key == ord("/"):
            search = prompt_input(stdscr, "search> ", initial=search)
            selected = 0
            scroll = 0
            status = f"Filtered rows with search={search!r}." if search else "Cleared search filter."
        elif key == ord("s"):
            sort_index = (sort_index + 1) % len(SORT_KEYS)
            selected = 0
            scroll = 0
            status = f"Sorted by {SORT_KEYS[sort_index]}."
        elif key == ord("r"):
            reverse = not reverse
            selected = 0
            scroll = 0
            status = f"Sort direction: {'descending' if reverse else 'ascending'}."
        elif key == ord("i"):
            try:
                status = install_to_local()
            except Exception as exc:
                status = f"Install failed: {exc}"
        elif key == ord("u"):
            try:
                status = check_for_update()
            except Exception as exc:
                status = f"Update check failed: {exc}"
        elif key in (10, 13, curses.KEY_ENTER):
            if visible_rows:
                return resume_with_terminal(visible_rows[selected].session_id)


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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["tui"]
    elif argv[0] not in {"list", "tui", "resume", "-h", "--help"}:
        argv = ["tui", *argv]

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
