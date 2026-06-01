import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required in .env")

_raw_users = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS: set[str] = set(_raw_users.split(",")) if _raw_users else set()

DOWNLOADS_DIR: str = os.getenv("DOWNLOADS_DIR", "downloads")
AUDIO_QUALITY: str = os.getenv("AUDIO_QUALITY", "320")

SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
