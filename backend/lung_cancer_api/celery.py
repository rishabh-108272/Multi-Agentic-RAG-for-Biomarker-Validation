import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lung_cancer_api.settings")

app = Celery("lung_cancer_api")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

