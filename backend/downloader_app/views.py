"""
downloader_app/views.py

Two endpoints:
  POST /api/video-info/   -> inspect a YouTube URL, return title/thumbnail/available formats
  POST /api/download/     -> download the chosen format (yt-dlp merges video+audio for
                              resolutions like 4K where YouTube serves them as separate
                              streams) and stream the resulting file back to the client.

Requires `ffmpeg` to be installed and on PATH so yt-dlp can mux separate 4K video-only
streams with an audio stream into a single mp4.
"""
import os
import re
import tempfile
import uuid

import yt_dlp
from django.conf import settings
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

YOUTUBE_URL_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)


def _validate_youtube_url(url: str) -> bool:
    return bool(url) and bool(YOUTUBE_URL_RE.match(url.strip()))


def _cookie_opts() -> dict:
    """
    Optional: pull cookies from a browser you're already logged into YouTube
    with, for videos that otherwise return "Please sign in" (age-restricted,
    or YouTube's bot-check on some videos). Set YTDLP_COOKIES_BROWSER in your
    environment, e.g. "chrome", "firefox", "edge", "brave" — only do this for
    your own account and content you have rights to access.
    """
    browser = os.environ.get("YTDLP_COOKIES_BROWSER")
    if browser:
        return {"cookiesfrombrowser": (browser,)}
    return {}


def _estimate_bytes(fmt: dict, duration) -> int | None:
    """
    Fall back to a bitrate-based estimate when yt-dlp doesn't give us an exact
    filesize (common for adaptive/DASH formats YouTube doesn't pre-compute a
    size for).
    """
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if size:
        return size
    tbr = fmt.get("tbr") or fmt.get("vbr") or fmt.get("abr")
    if tbr and duration:
        # tbr is in kbit/s
        return int(tbr * 1000 / 8 * duration)
    return None


def _is_real_video_format(f: dict) -> bool:
    """
    yt-dlp lists storyboard/scrubbing-preview sprite sheets alongside real
    video formats. Their "height" can be close to the real video's height, so
    checking vcodec alone isn't reliable — check every signal storyboards
    carry.
    """
    if not f.get("height"):
        return False
    if f.get("ext") == "mhtml":
        return False
    if (f.get("format_note") or "").lower() == "storyboard":
        return False
    if str(f.get("format_id", "")).startswith("sb"):
        return False
    if f.get("vcodec") in (None, "none"):
        return False
    return True


@api_view(["POST"])
def video_info(request):
    """Return metadata + a curated list of downloadable formats (including 4K if available)."""
    url = request.data.get("url", "").strip()

    if not _validate_youtube_url(url):
        return Response({"error": "Please provide a valid YouTube URL."}, status=400)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        **_cookie_opts(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        return Response({"error": f"Could not read this video: {exc}"}, status=400)

    duration = info.get("duration")
    all_formats = info.get("formats", [])

    video_formats = [f for f in all_formats if _is_real_video_format(f)]

    # Best standalone audio track, used to estimate the final muxed size for
    # video-only formats (anything above ~1080p is typically video-only and
    # gets combined with this track at download time).
    audio_formats = [
        f for f in all_formats
        if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")
    ]
    best_audio = max(audio_formats, key=lambda f: f.get("abr") or 0, default=None)
    best_audio_size = _estimate_bytes(best_audio, duration) if best_audio else 0

    # Build a de-duplicated list of the best format per resolution.
    seen_resolutions = {}
    for f in video_formats:
        height = f["height"]
        ext = f.get("ext")

        video_size = _estimate_bytes(f, duration)
        has_audio = f.get("acodec") not in (None, "none")
        total_size = video_size + (0 if has_audio else best_audio_size) if video_size else None

        candidate = {
            "format_id": f["format_id"],
            "resolution": f"{height}p" + (" (4K)" if height >= 2160 else ""),
            "height": height,
            "ext": ext,
            "fps": f.get("fps"),
            "filesize_approx": total_size,
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec"),
        }
        existing = seen_resolutions.get(height)
        if not existing or (ext == "mp4" and existing["ext"] != "mp4"):
            seen_resolutions[height] = candidate

    formats = sorted(seen_resolutions.values(), key=lambda x: x["height"], reverse=True)

    return JsonResponse(
        {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration,
            "uploader": info.get("uploader"),
            "formats": formats,
        }
    )


class _SelfDeletingFile:
    """
    Wraps an open file so that once Django finishes streaming it to the
    client (FileResponse calls .close() on the underlying file-like object
    when the response is done), the temp file is also removed from disk.
    This is what keeps tmp_downloads/ from filling up over time.
    """

    def __init__(self, file_obj, filepath):
        self._file = file_obj
        self._filepath = filepath

    def __getattr__(self, name):
        # Delegate read(), seek(), etc. straight to the real file object.
        return getattr(self._file, name)

    def __iter__(self):
        return iter(self._file)

    def close(self):
        try:
            self._file.close()
        finally:
            try:
                os.remove(self._filepath)
            except OSError:
                pass  # already gone, or never existed — fine either way


@api_view(["POST"])
def download_video(request):
    """
    Download the requested format_id and stream the resulting file to the client.

    For formats above 1080p, YouTube typically only exposes video-only streams, so we ask
    yt-dlp to also grab the best audio and let ffmpeg mux them into one mp4 file
    (format string: "<format_id>+bestaudio/best").
    """
    url = request.data.get("url", "").strip()
    format_id = request.data.get("format_id", "").strip()

    if not _validate_youtube_url(url):
        return Response({"error": "Please provide a valid YouTube URL."}, status=400)
    if not format_id:
        return Response({"error": "format_id is required."}, status=400)

    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    job_id = uuid.uuid4().hex
    output_template = os.path.join(settings.MEDIA_ROOT, f"{job_id}.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": f"{format_id}+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        **_cookie_opts(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            # merge_output_format may change the extension to mp4 after muxing
            if not os.path.exists(filepath):
                filepath = os.path.splitext(filepath)[0] + ".mp4"
    except yt_dlp.utils.DownloadError as exc:
        return Response({"error": f"Download failed: {exc}"}, status=400)

    safe_title = re.sub(r"[^\w\-. ]", "_", info.get("title", "video"))
    filename = f"{safe_title}.mp4"

    file_size = os.path.getsize(filepath)
    wrapped_file = _SelfDeletingFile(open(filepath, "rb"), filepath)

    response = FileResponse(wrapped_file, as_attachment=True, filename=filename)
    response["Content-Length"] = file_size
    return response
