#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import stat
import sys
import urllib.request
from pathlib import Path

DEFAULT_SCRIPT_URL = "https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py"
DEFAULT_BIN_DIR = Path("~/.local/bin").expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ls-cx-ss-install",
        description="Install ls-cx-ss from the GitHub Pages single-file distribution.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_SCRIPT_URL,
        help="Script URL to install from.",
    )
    parser.add_argument(
        "--bin-dir",
        default=str(DEFAULT_BIN_DIR),
        help="Target directory for the installed command.",
    )
    parser.add_argument(
        "--name",
        default="ls-cx-ss",
        help="Installed command name.",
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="Print the installed path after success.",
    )
    return parser


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target_dir = Path(args.bin_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / args.name

    script_text = download_text(args.url)
    target_path.write_text(script_text, encoding="utf-8")
    ensure_executable(target_path)

    print(f"installed: {target_path}")
    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"note: add {target_dir} to PATH if needed", file=sys.stderr)
    if args.print_path:
        print(target_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
