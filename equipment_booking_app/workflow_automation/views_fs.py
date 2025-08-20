import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET

from utils.paths import list_windows_drives, resolve_user_path_or_raise


@require_GET
@login_required
def list_fs(request):
    """List directories and files for a given path.

    When no ``path`` query parameter is supplied, the allowed filesystem roots
    or available Windows drives are returned.
    """
    user_path = request.GET.get("path")
    if not user_path:
        roots = getattr(settings, "ALLOWED_FS_ROOTS", [])
        dirs = roots[:] if roots else list_windows_drives()
        if not dirs:
            dirs = [os.path.sep]
        return JsonResponse({"path": "", "dirs": dirs, "files": []})

    abs_path = resolve_user_path_or_raise(user_path)
    if not os.path.isdir(abs_path):
        raise Http404("Directory does not exist")

    entries = sorted(os.listdir(abs_path))
    dirs = [e for e in entries if os.path.isdir(os.path.join(abs_path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(abs_path, e))]

    parent = None
    current = Path(abs_path)
    if getattr(settings, "ALLOWED_FS_ROOTS", []):
        allowed = [Path(r).resolve() for r in settings.ALLOWED_FS_ROOTS]
        if current.parent != current and any(str(current.parent).lower().startswith(str(r).lower()) for r in allowed):
            parent = str(current.parent)
    else:
        parent = str(current.parent) if current.parent != current else None

    return JsonResponse({"path": abs_path, "parent": parent, "dirs": dirs, "files": files})
