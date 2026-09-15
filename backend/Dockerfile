# Deploy target: Render (or any Docker-based host). Installs ffmpeg, which
# yt-dlp needs to merge separate 4K video + audio streams.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/tmp_downloads

ENV PYTHONUNBUFFERED=1

# Render sets $PORT; default to 8000 for local `docker run`
CMD gunicorn project.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 300
