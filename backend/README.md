---
title: Genix Ai Backend
emoji: 🌍
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Django backend for serving biomarker models.
dockerbuildargs:
  REQUIREMENTS_FILE: requirements-hf-space.txt
---

## Hugging Face Spaces

This Space uses Docker with a **slim dependency file** (`requirements-hf-space.txt`) so the image can build and start within HF timeouts. It omits `torch` / `transformers` / `sentence-transformers`, which are not imported by this backend (classification calls remote HF Spaces).

- **Port:** The app listens on `0.0.0.0:$PORT`. `README` frontmatter sets `app_port: 7860`, and the Dockerfile defaults `PORT=7860`.
- **Channels:** By default the channel layer is **in-memory** (no Redis in the container). To use Redis for WebSockets, set `CHANNEL_LAYER_REDIS=true` and provide `REDIS_HOST` / `REDIS_PORT`, and install from full `requirements.txt` (includes `channels-redis`).

### Optional: full dependency image

To build with the complete `requirements.txt` (e.g. local embedding models later), remove or override `dockerbuildargs` in this README, or build with:

`docker build --build-arg REQUIREMENTS_FILE=requirements.txt .`

Configuration reference: https://huggingface.co/docs/hub/spaces-config-reference
