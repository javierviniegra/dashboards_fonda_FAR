"""Bridge to Central de Reportes' engine (vendor/central, a git submodule).

Every number this app shows is computed by `central.motor` (tested and
approved in Central). This module is the one place that knows where that
code lives and which commit of it is in use, so each figure can be traced
to an exact version of the code that produced it.

Central's Django apps (`central`, `cuentas`) are NOT installed here: only
the engine is imported, as a library. Updating the engine = moving the
submodule to another commit on purpose and re-running the tests.
"""

import subprocess
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def version() -> str:
    """Short commit of the engine in use ("desconocida" if git cannot tell)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(settings.CENTRAL_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip() or "desconocida"
    except (OSError, subprocess.SubprocessError):
        return "desconocida"


def cambios_locales() -> list[str]:
    """Files of the submodule that differ from the pinned commit (tracked
    files only; `__pycache__` is untracked and ignored). Must be empty."""
    out = subprocess.run(
        ["git", "-C", str(settings.CENTRAL_DIR), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return [linea[3:] for linea in out.stdout.splitlines() if linea.strip()]


def disponible() -> bool:
    """True when the engine can be imported from the submodule."""
    try:
        import central.motor.periodos  # noqa: F401
    except ImportError:
        return False
    return True
