import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

function formatSize(bytes) {
  if (!bytes) return "size unknown";
  const mb = bytes / (1024 * 1024);
  const value = mb > 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(0)} MB`;
  return `≈ ${value}`;
}

function formatDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function YouTubeDownloader() {
  const [url, setUrl] = useState("");
  const [video, setVideo] = useState(null);
  const [selectedFormat, setSelectedFormat] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | fetching | ready | downloading | error
  const [errorMsg, setErrorMsg] = useState("");

  async function handleFetchInfo(e) {
    e.preventDefault();
    setStatus("fetching");
    setErrorMsg("");
    setVideo(null);
    setSelectedFormat(null);

    try {
      const res = await fetch(`${API_BASE}/video-info/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      setVideo(data);
      setSelectedFormat(data.formats?.[0]?.format_id ?? null);
      setStatus("ready");
    } catch (err) {
      setErrorMsg(err.message);
      setStatus("error");
    }
  }

  async function handleDownload() {
    if (!selectedFormat) return;
    setStatus("downloading");
    setErrorMsg("");

    try {
      const res = await fetch(`${API_BASE}/download/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, format_id: selectedFormat }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Download failed.");
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      // Prefer the RFC 5987 filename*=UTF-8''... form (correctly handles
      // non-ASCII titles), falling back to a plain quoted filename="...".
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const plainMatch = disposition.match(/filename="([^"]+)"/i);
      const filename = utf8Match
        ? decodeURIComponent(utf8Match[1])
        : plainMatch
        ? plainMatch[1]
        : "video.mp4";

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
      setStatus("ready");
    } catch (err) {
      setErrorMsg(err.message);
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen bg-[#0E1013] text-[#E7E5DF] flex flex-col items-center px-6 py-16">
      <div className="w-full max-w-xl">
        <h1 className="text-3xl font-semibold tracking-tight text-[#F2A65A]">
          Fetch
        </h1>
        <p className="mt-2 text-sm text-[#9A9890] leading-relaxed max-w-md">
          Paste a link, pick a resolution, get the file. Supports resolutions
          up to 4K where the source provides them.
        </p>

        <form onSubmit={handleFetchInfo} className="mt-8 flex gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="flex-1 bg-[#181B20] border border-[#2A2E35] rounded-md px-4 py-3 text-sm placeholder-[#5C5A54] focus:outline-none focus:ring-2 focus:ring-[#F2A65A]/60"
          />
          <button
            type="submit"
            disabled={status === "fetching" || !url}
            className="px-5 py-3 rounded-md bg-[#F2A65A] text-[#0E1013] text-sm font-medium disabled:opacity-40 hover:bg-[#f5b876] transition-colors"
          >
            {status === "fetching" ? "Looking up..." : "Look up"}
          </button>
        </form>

        {status === "error" && (
          <p className="mt-4 text-sm text-[#E1685A]">{errorMsg}</p>
        )}

        {video && (
          <div className="mt-10 border-t border-[#2A2E35] pt-8">
            <div className="flex gap-4">
              {video.thumbnail && (
                <img
                  src={video.thumbnail}
                  alt=""
                  className="w-32 h-20 object-cover rounded-md flex-shrink-0"
                />
              )}
              <div className="min-w-0">
                <h2 className="text-base font-medium truncate">
                  {video.title}
                </h2>
                <p className="text-xs text-[#9A9890] mt-1">
                  {video.uploader} · {formatDuration(video.duration)}
                </p>
              </div>
            </div>

            <fieldset className="mt-6">
              <legend className="text-xs text-[#9A9890] mb-3">
                Choose a resolution
              </legend>
              <div className="grid grid-cols-2 gap-2">
                {video.formats.map((f) => (
                  <label
                    key={f.format_id}
                    className={`flex items-center justify-between gap-2 px-4 py-3 rounded-md border cursor-pointer text-sm transition-colors ${
                      selectedFormat === f.format_id
                        ? "border-[#F2A65A] bg-[#F2A65A]/10"
                        : "border-[#2A2E35] hover:border-[#3A3E45]"
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="format"
                        className="accent-[#F2A65A]"
                        checked={selectedFormat === f.format_id}
                        onChange={() => setSelectedFormat(f.format_id)}
                      />
                      {f.resolution}
                    </span>
                    <span className="text-xs text-[#7A786F]">
                      {formatSize(f.filesize_approx)}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <button
              onClick={handleDownload}
              disabled={status === "downloading" || !selectedFormat}
              className="mt-6 w-full py-3 rounded-md bg-[#F2A65A] text-[#0E1013] text-sm font-medium disabled:opacity-40 hover:bg-[#f5b876] transition-colors"
            >
              {status === "downloading" ? "Downloading..." : "Download"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
