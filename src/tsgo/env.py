"""Environment loading helpers.

The project keeps `.env` out of git. This helper loads local `.env` files when
`python-dotenv` is installed, but it never makes dotenv a hard dependency for
core graph execution.
"""

from __future__ import annotations

from pathlib import Path


def load_env_file(path: str | None = None, *, override: bool = False) -> bool:
    """Load a dotenv file if python-dotenv is available.

    Returns True when a dotenv loader was available and executed, False when the
    optional dependency is not installed.
    """

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    env_path = Path(path or ".env")
    load_dotenv(dotenv_path=env_path if env_path.exists() else None, override=override)
    return True
