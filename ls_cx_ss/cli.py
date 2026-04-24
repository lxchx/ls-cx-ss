import argparse
import json
import os
import shutil
import sys
from typing import List, Optional

from ls_cx_ss.query import SORT_KEYS, filter_rows, sort_rows
from ls_cx_ss.render import compute_column_widths, format_header, format_row
from ls_cx_ss.scanner import load_sessions
from ls_cx_ss.timefmt import ago
from ls_cx_ss.tui import launch_tui, resume_with_terminal

KNOWN_COMMANDS = {"list", "tui", "resume"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ls-cx-ss")
    sub = parser.add_subparsers(dest="command")

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


def materialize_rows(args) -> list:
    rows = load_sessions(cwd=os.getcwd(), all_cwds=args.all_cwds)
    rows = filter_rows(rows, args.search)
    rows = sort_rows(rows, sort_key=args.sort, reverse=resolve_reverse(args.sort, args.reverse))
    return rows


def print_table(rows: list, show_cwd: bool) -> None:
    widths = compute_column_widths(rows, shutil.get_terminal_size((160, 24)).columns - 1, show_cwd=show_cwd)
    print(format_header(widths, show_cwd=show_cwd))
    for row in rows:
        print(format_row(row, widths, show_cwd=show_cwd))


def print_json(rows: list) -> None:
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


def normalize_argv(argv: List[str]) -> List[str]:
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


def main(argv: Optional[List[str]] = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))

    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.error("a command is required")

    if args.command == "resume":
        return resume_session(args.session_id)

    rows = materialize_rows(args)
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
