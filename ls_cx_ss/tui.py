from __future__ import annotations

import curses
import os
import shutil
from contextlib import contextmanager
from collections.abc import Sequence

from ls_cx_ss.model import SessionRow
from ls_cx_ss.query import SORT_KEYS, filter_rows, sort_rows
from ls_cx_ss.render import compute_column_widths, format_header, format_row, truncate_display

KEY_ESC = 27


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
    try:
        os.dup2(tty_fd, 0)
        os.dup2(tty_fd, 1)
        yield
    finally:
        os.dup2(saved_stdin, 0)
        os.dup2(saved_stdout, 1)
        os.close(saved_stdin)
        os.close(saved_stdout)
        os.close(tty_fd)


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
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    title = f"ls-cx-ss  cwd={os.getcwd()}  rows={len(visible_rows)}/{len(all_rows)}"
    hint = f"/ search  s sort({sort_key})  r reverse({reverse})  Enter resume  q/Esc quit"
    stdscr.addnstr(0, 0, truncate_display(title, width - 1), width - 1, curses.A_BOLD)
    if search:
        stdscr.addnstr(1, 0, truncate_display(f"search: {search}", width - 1), width - 1)
        header_row = 3
    else:
        header_row = 2

    widths = compute_column_widths(visible_rows or all_rows, width - 1, show_cwd=show_cwd)
    stdscr.addnstr(header_row, 0, format_header(widths, show_cwd=show_cwd), width - 1, curses.A_BOLD)

    list_top = header_row + 1
    list_height = max(1, height - list_top - 1)
    for idx, row in enumerate(visible_rows[scroll : scroll + list_height]):
        attr = curses.A_REVERSE if scroll + idx == selected else curses.A_NORMAL
        stdscr.addnstr(
            list_top + idx,
            0,
            format_row(row, widths, show_cwd=show_cwd),
            width - 1,
            attr,
        )
    stdscr.addnstr(height - 1, 0, truncate_display(hint, width - 1), width - 1)
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

    while True:
        current_sort = SORT_KEYS[sort_index]
        visible_rows = materialize_rows(rows, search, current_sort, reverse)
        if selected >= len(visible_rows):
            selected = max(0, len(visible_rows) - 1)

        height, _ = stdscr.getmaxyx()
        header_rows = 4 if search else 3
        list_height = max(1, height - header_rows - 1)
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
        elif key == ord("s"):
            sort_index = (sort_index + 1) % len(SORT_KEYS)
            selected = 0
            scroll = 0
        elif key == ord("r"):
            reverse = not reverse
            selected = 0
            scroll = 0
        elif key in (10, 13, curses.KEY_ENTER):
            if visible_rows:
                return visible_rows[selected].session_id


def launch_tui(
    rows: Sequence[SessionRow], sort_key: str = "updated", reverse: bool = True, show_cwd: bool = False
) -> str | None:
    if shutil.which("codex") is None:
        raise RuntimeError("`codex` not found in PATH.")
    with attached_terminal():
        return curses.wrapper(run_picker, rows, sort_key, reverse, show_cwd)
