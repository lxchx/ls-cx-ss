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
    match = VERSION_RE.search(download_text(url))
    if not match:
        return None
    return match.group(1) or match.group(2)


def check_for_update(current_version: str = __version__, url: str = DEFAULT_SCRIPT_URL) -> str:
    latest = remote_version(url)
    if not latest:
        return "Update check failed: could not read remote version."
    if _parse_version(latest) > _parse_version(current_version):
        return (
            f"Update available: {current_version} -> {latest}. "
            "Press uppercase I to install/update ~/.local/bin/ls-cx-ss."
        )
    if _parse_version(latest) == _parse_version(current_version):
        return f"Already up to date: {current_version}."
    return f"Running newer build: {current_version} (remote {latest})."
