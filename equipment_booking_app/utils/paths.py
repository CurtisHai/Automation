import os
import string
from pathlib import Path
import platform

from django.conf import settings


def list_windows_drives():
    """Return a list of existing Windows drive letters."""
    if platform.system().lower() != "windows":
        return []
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:" + os.sep
        if os.path.exists(drive):
            drives.append(drive)
    return drives


def resolve_user_path_or_raise(path: str) -> str:
    """Validate and normalize a user provided path.

    The path must be absolute and reside under one of the roots specified in
    ``settings.ALLOWED_FS_ROOTS`` when that setting is non-empty.
    """
    if not path:
        raise ValueError("Path is required")

    p = Path(path).expanduser()
    try:
        p = p.resolve(strict=False)
    except Exception as exc:  # pragma: no cover - safeguard
        raise ValueError(str(exc))

    if not p.is_absolute():
        raise ValueError("Path must be absolute")

    roots = getattr(settings, "ALLOWED_FS_ROOTS", [])
    if roots:
        allowed = [Path(r).expanduser().resolve(strict=False) for r in roots]
        if not any(str(p).lower().startswith(str(r).lower()) for r in allowed):
            raise ValueError("Path not under allowed roots")

    return str(p)
