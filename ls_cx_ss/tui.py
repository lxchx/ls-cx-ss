from __future__ import annotations

import curses
import os
import shutil
from contextlib import contextmanager
from collections.abc import Sequence

from ls_cx_ss import __version__
from ls_cx_ss.distribution import check_for_update, install_to_local
from ls_cx_ss.model import SessionRow
from ls_cx_ss.query import SORT_KEYS, filter_rows, sort_rows
from ls_cx_ss.render import GUTTER, compute_column_widths, format_row, header_label, pad_display, truncate_display

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
        label = pad_display(header_label(key, sort_key, reverse), cell_width)
        attr = curses.A_BOLD
        if key == sort_key:
            attr |= curses.A_REVERSE
        stdscr.addnstr(row_y, x, label, max(0, width - x), attr)
        x += cell_width
        if idx != len(fields) - 1:
            stdscr.addnstr(row_y, x, " " * GUTTER, max(0, width - x))
            x += GUTTER


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
    title = f"ls-cx-ss v{__version__}  cwd={os.getcwd()}  rows={len(visible_rows)}/{len(all_rows)}"
    hint = f"/ search  s sort  r reverse  i install  u update  Enter resume  q/Esc quit"
    stdscr.addnstr(0, 0, truncate_display(title, width - 1), width - 1, curses.A_BOLD)
    meta_row = 1
    if status:
        stdscr.addnstr(meta_row, 0, truncate_display(status, width - 1), width - 1)
        meta_row += 1
    if search:
        stdscr.addnstr(meta_row, 0, truncate_display(f"search: {search}", width - 1), width - 1)
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
