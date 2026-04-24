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
from ls_cx_ss.render import (
    GUTTER,
    display_slice,
    display_width,
    format_row,
    full_column_widths,
    header_label,
    pad_display,
    table_width,
    truncate_display,
)

KEY_ESC = 27
KEY_TAB = 9
KEY_BACKSPACE_CODES = {curses.KEY_BACKSPACE, 127, 8}
TUI_SORT_KEYS = ("updated", "created")


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
