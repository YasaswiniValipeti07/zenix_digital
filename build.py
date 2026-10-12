"""Vercel Django build hook: create/update schema before serving requests."""

import os
import subprocess
import sys


def main():
    environment = os.environ.copy()
    environment.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # All migrations in this project are additive. In Vercel, DATABASE_URL should
    # point to a persistent managed PostgreSQL database; without it, this migrates
    # the build's SQLite file, which is suitable only for a disposable demo.
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        check=True,
        env=environment,
    )


if __name__ == "__main__":
    main()
