"""
WSGI config for lung_cancer_api project.

It exposes the WSGI callable as a module-level variable named ``application``.

Migrations are applied on import (with a file lock on POSIX) so container platforms
that do not run `manage.py migrate` before Gunicorn (e.g. some Hugging Face / PaaS
setups) still get a valid SQLite schema before the first request.
"""

import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lung_cancer_api.settings")

import django

django.setup()


def _apply_migrations() -> None:
    from django.conf import settings
    from django.core.management import call_command

    lock_path = Path(settings.BASE_DIR) / ".wsgi_migrate.lock"
    lock_f = open(lock_path, "a+")
    try:
        try:
            import fcntl  # type: ignore[attr-defined]

            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        except ImportError:
            # Windows / non-POSIX: no lock; single dev process is fine.
            pass
        call_command("migrate", "--noinput", verbosity=0)
    finally:
        try:
            import fcntl  # type: ignore[attr-defined]

            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock_f.close()


_apply_migrations()

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
