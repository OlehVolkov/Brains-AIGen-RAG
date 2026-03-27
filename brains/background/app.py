from __future__ import annotations

from huey import SqliteHuey

from brains.background.jobs import ensure_background_dirs
from brains.config import resolve_background_paths


paths = resolve_background_paths()
ensure_background_dirs(paths)

huey = SqliteHuey("brains-background", filename=str(paths.queue_path))

# Import task registrations after creating the Huey instance.
from brains.background import tasks as _tasks  # noqa: E402,F401
