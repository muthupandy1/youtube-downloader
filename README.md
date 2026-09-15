# YouTube Downloader (Django + React)

A complete, ready-to-run full-stack video downloader: paste a URL, pick a
resolution (including 4K when the source video offers it), download the
file.

## ⚠️ Before you use this

Downloading videos from YouTube generally **violates YouTube's Terms of
Service** unless:
- you own the video (your own channel's uploads), or
- the video is explicitly licensed for download/reuse (e.g. Creative
  Commons), or
- you have some other clear right to the content.

This code is provided as a technical reference. You are responsible for how
you use it — check your local copyright law and YouTube's ToS for your use
case.

## Project structure

```
youtube-downloader/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── project/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── downloader_app/
│       ├── apps.py
│       ├── views.py
│       └── urls.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── YouTubeDownloader.jsx
        └── index.css
```

## How 4K works here

YouTube usually serves anything above 1080p (including 4K/2160p) as a
**video-only** stream, with audio provided separately. `yt-dlp` and `ffmpeg`
handle this automatically: the backend requests `<format_id>+bestaudio` and
`ffmpeg` muxes them into a single `.mp4`. This is why **ffmpeg is a hard
requirement**, not optional.

## Backend setup (Django)

```bash
# 1. System dependency — required for merging 4K video + audio
sudo apt install ffmpeg        # macOS: brew install ffmpeg

# 2. Python environment
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Run it — everything (settings, urls, app) is already wired up
python manage.py migrate
python manage.py runserver
```

Backend runs at `http://localhost:8000`.

### API

**POST `/api/video-info/`**
```json
{ "url": "https://www.youtube.com/watch?v=..." }
```
Returns title, thumbnail, duration, and a list of available resolutions
(deduplicated per height, mp4 preferred), e.g.:
```json
{
  "title": "...",
  "thumbnail": "...",
  "formats": [
    { "format_id": "313", "resolution": "2160p (4K)", "height": 2160, "ext": "webm", ... },
    { "format_id": "137", "resolution": "1080p", "height": 1080, "ext": "mp4", ... }
  ]
}
```

**POST `/api/download/`**
```json
{ "url": "https://www.youtube.com/watch?v=...", "format_id": "313" }
```
Streams the merged `.mp4` file back as an attachment.

## Frontend setup (React + Vite + Tailwind)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and talks to the Django API at
`http://localhost:8000/api` (see `API_BASE` in `src/YouTubeDownloader.jsx`
if you need to change this, e.g. for a deployed backend).

## Running both together

Open two terminals:
```bash
# Terminal 1
cd backend && source venv/bin/activate && python manage.py runserver

# Terminal 2
cd frontend && npm run dev
```
Then visit `http://localhost:5173`.

## Deploying (free tier)

**Frontend → Vercel (or Netlify/Cloudflare Pages):**
1. Push this repo to GitHub.
2. Import it in Vercel, set the root directory to `frontend/`.
3. Add an environment variable `VITE_API_BASE` = your deployed backend URL +
   `/api` (e.g. `https://youtube-downloader-backend.onrender.com/api`).
4. Deploy. See `frontend/.env.example` for local equivalent.

**Backend → Render (free web service, Docker):**
1. Push this repo to GitHub.
2. In Render, "New Web Service" → connect the repo → root directory
   `backend/` → it will detect `Dockerfile` and `render.yaml` automatically.
3. Set the `CORS_ALLOWED_ORIGINS` env var to your deployed frontend's URL
   (from the Vercel step above) — comma-separate multiple origins if needed.
4. Deploy.

**Known limits of Render's free tier for this app:**
- Spins down after ~15 min idle; the first request after that takes ~30s to
  wake up.
- 512MB RAM / 0.1 vCPU — fine for 720p/1080p, but 4K muxing on a busy/large
  video can be tight. If you hit memory errors, that's why.
- No persistent disk — `tmp_downloads/` is wiped on every restart/redeploy,
  which is fine since files are meant to be temporary here.
- The current synchronous download endpoint can exceed Render's request
  timeout on very large 4K files — see the Celery note below if that bites
  you.

**Cleaning up temp files:**
Downloaded files delete themselves automatically the moment they finish
streaming to the browser (see `_SelfDeletingFile` in `views.py`) — this is
the main mechanism and needs no setup. As a safety net for downloads that
get interrupted or crash mid-stream, run:
```bash
python manage.py cleanup_temp_downloads --hours 1
```
Schedule this periodically in production — e.g. a free Render Cron Job
hitting `python manage.py cleanup_temp_downloads`, or a crontab entry if
you're on a VM (`0 * * * * cd /path/to/backend && venv/bin/python manage.py
cleanup_temp_downloads`).

**Alternative: your own server (more reliable, more setup)**
Oracle Cloud's "Always Free" tier gives you a real ARM VM (no sleep, more
RAM/CPU) you can install everything on yourself — Python, `ffmpeg`, Nginx,
`gunicorn`, and a systemd service. More setup work, but no cold starts and
no hard memory ceiling. If you go this route and make the app public, keep
in mind Oracle (and most providers) can and do act on copyright complaints
against hosted instances — this isn't hypothetical, it's happened to other
people running similar tools.



- **Long-running downloads**: the current `download_video` view runs
  synchronously — for large 4K files, offload the actual download to a
  Celery task and have the frontend poll a job-status endpoint, then serve
  the finished file (or a signed S3 URL) once ready. `celery` and `redis`
  are already in `requirements.txt` to make this easy to add.
- **Cleanup**: temporary files land in `backend/tmp_downloads/`; add a
  periodic task to delete files older than a few hours.
- **Rate limiting**: DRF anonymous throttling is already configured in
  `settings.py` (20 requests/minute) — tune `DEFAULT_THROTTLE_RATES` as
  needed.
- **Secret key / debug**: `SECRET_KEY` and `DEBUG=True` in `settings.py` are
  for local development only — replace with environment variables before
  deploying.
- **yt-dlp updates**: YouTube changes its internals often; keep `yt-dlp`
  updated (`pip install -U yt-dlp`) or downloads will start failing.
