import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)

MAX_FILESIZE_BYTES = 50 * 1024 * 1024  # 50 MB — Telegram bot limit


class MusicDownloader:
    def __init__(self, output_dir: str = "downloads", quality: str = "320"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality

    def _ydl_opts(self, output_template: str) -> dict:
        return {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.quality,
                },
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "max_filesize": MAX_FILESIZE_BYTES,
        }

    async def search_and_download(self, query: str) -> Optional[dict]:
        return await self._run_download(f"ytsearch1:{query}")

    async def download_url(self, url: str) -> Optional[dict]:
        return await self._run_download(url)

    async def _run_download(self, url: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_download, url)

    def _sync_download(self, url: str) -> Optional[dict]:
        file_id = str(uuid.uuid4())
        output_template = str(self.output_dir / f"{file_id}.%(ext)s")
        opts = self._ydl_opts(output_template)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None
                if "entries" in info:
                    if not info["entries"]:
                        return None
                    info = info["entries"][0]

            mp3_path = self.output_dir / f"{file_id}.mp3"
            if not mp3_path.exists():
                return None

            # Clean up thumbnail files yt-dlp may leave behind
            for ext in ("jpg", "jpeg", "png", "webp"):
                thumb = self.output_dir / f"{file_id}.{ext}"
                if thumb.exists():
                    thumb.unlink(missing_ok=True)

            size = mp3_path.stat().st_size
            if size > MAX_FILESIZE_BYTES:
                mp3_path.unlink(missing_ok=True)
                return {"error": "too_large"}

            return {
                "path": str(mp3_path),
                "title": info.get("title") or "Unknown",
                "artist": info.get("artist") or info.get("uploader") or "Unknown",
                "album": info.get("album") or "",
                "duration": int(info.get("duration") or 0),
            }

        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            logger.warning(f"yt-dlp DownloadError: {msg}")
            if "File is larger than max-filesize" in msg:
                return {"error": "too_large"}
            return None
        except Exception as e:
            logger.error(f"Unexpected download error: {e}")
            return None

    def cleanup(self, path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
