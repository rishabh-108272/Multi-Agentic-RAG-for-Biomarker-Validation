FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces expect port 7860; Railway/Render set PORT explicitly.
# Default to 7860 so Spaces health checks pass when PORT is unset.
ENV PORT=7860

# HF Space README can set dockerbuildargs REQUIREMENTS_FILE=requirements-hf-space.txt for faster builds.
ARG REQUIREMENTS_FILE=requirements.txt
COPY ${REQUIREMENTS_FILE} ./requirements-install.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-install.txt

COPY . .

EXPOSE 7860

# One worker keeps memory low on small Space hardware; migrate before serving.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn lung_cancer_api.wsgi:application --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 300 --graceful-timeout 60 --limit-request-line 8190"]
