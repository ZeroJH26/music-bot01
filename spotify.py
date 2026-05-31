import logging
import re
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_TRACK_RE = re.compile(r"https?://open\.spotify\.com/track/([A-Za-z0-9]+)")


def is_spotify_url(text: str) -> bool:
    return bool(_TRACK_RE.search(text))


async def get_track_query(url: str, client_id: str = "", client_secret: str = "") -> Optional[dict]:
    """Return {'search_query': str, 'title': str, 'artist': str} or None."""
    match = _TRACK_RE.search(url)
    if not match:
        return None

    if client_id and client_secret:
        result = await _via_api(match.group(1), client_id, client_secret)
        if result:
            return result

    return await _via_oembed(url)


async def _via_api(track_id: str, client_id: str, client_secret: str) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            token_resp = await session.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(client_id, client_secret),
                timeout=aiohttp.ClientTimeout(total=10),
            )
            token_data = await token_resp.json()
            token = token_data.get("access_token")
            if not token:
                return None

            track_resp = await session.get(
                f"https://api.spotify.com/v1/tracks/{track_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
            track = await track_resp.json()

        artists = ", ".join(a["name"] for a in track.get("artists", []))
        title = track.get("name", "")
        album = track.get("album", {}).get("name", "")
        return {
            "title": title,
            "artist": artists,
            "album": album,
            "search_query": f"{artists} - {title}",
        }
    except Exception as e:
        logger.error(f"Spotify API error: {e}")
        return None


async def _via_oembed(url: str) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"https://open.spotify.com/oembed?url={url}",
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if resp.status != 200:
                return None
            data = await resp.json()
        title = data.get("title", "")
        return {"title": title, "artist": "", "album": "", "search_query": title}
    except Exception as e:
        logger.error(f"Spotify oEmbed error: {e}")
        return None
