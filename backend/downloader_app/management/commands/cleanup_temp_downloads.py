"""
Deletes files in MEDIA_ROOT (tmp_downloads/) older than --hours.

This is a safety net, not the primary cleanup mechanism — normal downloads
already delete themselves as soon as they finish streaming (see
_SelfDeletingFile in downloader_app/views.py). This command only catches
leftovers from downloads that got interrupted, crashed mid-stream, or were
never picked up by a client.

Usage:
    python manage.py cleanup_temp_downloads              # default: 1 hour
    python manage.py cleanup_temp_downloads --hours 6

Schedule this periodically in production, e.g. as a Render Cron Job, a
crontab entry on a VM, or a Celery beat task.
"""
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete orphaned files in MEDIA_ROOT older than --hours (default: 1)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=float,
            default=1.0,
            help="Delete files older than this many hours (default: 1).",
        )

    def handle(self, *args, **options):
        max_age_seconds = options["hours"] * 3600
        media_root = settings.MEDIA_ROOT

        if not os.path.isdir(media_root):
            self.stdout.write("Nothing to clean up — tmp_downloads/ doesn't exist yet.")
            return

        now = time.time()
        removed = 0
        for name in os.listdir(media_root):
            path = os.path.join(media_root, name)
            if not os.path.isfile(path):
                continue
            age = now - os.path.getmtime(path)
            if age > max_age_seconds:
                try:
                    os.remove(path)
                    removed += 1
                except OSError as exc:
                    self.stderr.write(f"Could not remove {path}: {exc}")

        self.stdout.write(f"Removed {removed} orphaned file(s) older than {options['hours']}h.")
