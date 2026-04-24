import os
import re
import shutil
import stat
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from ls_cx_ss import __version__

DEFAULT_SCRIPT_URL = "https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py"
DEFAULT_BIN_DIR = Path("~/.local/bin").expanduser()
DEFAULT_COMMAND_NAME = "ls-cx-ss"
VERSION_RE = re.compile(r'APP_VERSION = "([^"]+)"|__version__ = "([^"]+)"')


def download_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except Exception:
        curl = shutil.which("curl")
        if not curl:
            raise
        return subprocess.check_output([curl, "-fsSL", url]).decode("utf-8")


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_version(raw: str) -> Optional[str]:
    match = VERSION_RE.search(raw)
    if not match:
        return None
    return match.group(1) or match.group(2)


def install_to_local(
    url: str = DEFAULT_SCRIPT_URL,
    bin_dir: Path = DEFAULT_BIN_DIR,
    command_name: str = DEFAULT_COMMAND_NAME,
) -> str:
    target_dir = Path(bin_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / command_name
    target_path.write_text(download_text(url), encoding="utf-8")
    ensure_executable(target_path)

    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if str(target_dir) not in path_entries:
        return f"Installed to {target_path}. Add {target_dir} to PATH if needed."
    return f"Installed to {target_path}."


def _parse_version(raw: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for item in raw.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            break
    return tuple(parts)


def remote_version(url: str = DEFAULT_SCRIPT_URL) -> Optional[str]:
    return _extract_version(download_text(url))


def installed_version(
    bin_dir: Path = DEFAULT_BIN_DIR,
    command_name: str = DEFAULT_COMMAND_NAME,
) -> Optional[str]:
    target_path = Path(bin_dir).expanduser() / command_name
    if not target_path.exists():
        return None
    try:
        return _extract_version(target_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def check_for_update(current_version: str = __version__, url: str = DEFAULT_SCRIPT_URL) -> str:
    effective_current = installed_version() or current_version
    latest = remote_version(url)
    if not latest:
        return "Update check failed: could not read remote version."
    if _parse_version(latest) > _parse_version(effective_current):
        return (
            f"Update available: {effective_current} -> {latest}. "
            "Press uppercase I to install/update ~/.local/bin/ls-cx-ss."
        )
    if _parse_version(latest) == _parse_version(effective_current):
        return f"Already up to date: {effective_current}."
    return f"Running newer build: {effective_current} (remote {latest})."
