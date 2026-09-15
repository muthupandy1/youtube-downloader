"""
Django settings for the YouTube downloader backend.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_list(name: str, default: list) -> list:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Security -----------------------------------------------------------
# In production (Render etc.), set SECRET_KEY, DEBUG=False, ALLOWED_HOSTS,
# and CORS_ALLOWED_ORIGINS as environment variables — never commit real
# values for these.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# --- Apps -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "downloader_app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must be near the top
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"

# --- Database ---------------------------------------------------------
# SQLite is enough here since this project has no real models yet.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Project-specific settings ----------------------------------------

# Origin(s) allowed to call this API — add your deployed frontend URL here,
# e.g. CORS_ALLOWED_ORIGINS=https://your-app.vercel.app in Render's env vars.
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)

# Without this, browsers block JS from reading Content-Disposition on
# cross-origin responses (frontend :5173 -> backend :8000 counts as
# cross-origin), so the real filename never reaches the download code and it
# falls back to a generic name every time.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

# Where temporary downloaded files are stored before being streamed to the client
MEDIA_ROOT = BASE_DIR / "tmp_downloads"
FILE_UPLOAD_MAX_MEMORY_SIZE = 0  # stream large files instead of buffering in RAM

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/minute",
    },
}

# yt-dlp needs ffmpeg on PATH to merge separate 4K video + audio streams.
# Install it system-wide, e.g.: sudo apt install ffmpeg
