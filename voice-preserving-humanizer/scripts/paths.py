"""Private storage path helpers (plan §6.3)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PROFILE_ROOT = Path.home() / ".local" / "share" / "voice-preserving-humanizer" / "profiles"


def profile_root() -> Path:
    raw = os.environ.get("VOICE_PROFILE_DIR")
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_PROFILE_ROOT


def profile_dir(profile_name: str) -> Path:
    return profile_root() / profile_name


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private_file(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)
    os.chmod(path, 0o600)
