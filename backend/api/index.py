import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lung_cancer_api.settings")

# Vercel's Python runtime expects a module-level callable named `app`.
app = get_wsgi_application()

