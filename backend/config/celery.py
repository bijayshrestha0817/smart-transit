"""Celery application. Tasks live in apps/*/tasks.py and backend/celery_tasks/."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("smart_transit")

# Pull CELERY_* keys from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed app.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - smoke task
    print(f"Request: {self.request!r}")
