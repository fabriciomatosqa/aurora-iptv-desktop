"""Choose trustworthy artwork metadata without guessing by title.

The stream/provider metadata is the source of truth. No web-search or image
matching by fuzzy titles: a wrong cover is worse than a neutral placeholder.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from pathlib import PureWindowsPath
from urllib.parse import unquote, urlsplit

CHANNEL_KEYS = ("logo_path", "tvg-logo", "tvg_logo", "stream_icon", "logo",
                "icon", "image", "thumb", "thumbnail")
MOVIE_KEYS = ("poster_path", "poster", "cover", "stream_icon", "tvg-logo",
              "tvg_logo", "logo", "thumb", "thumbnail", "image")
SERIES_KEYS = ("series_poster_path", "series_poster", "poster_path",
               "poster", "cover", "tvg-logo", "tvg_logo", "logo",
               "thumb", "thumbnail", "image", "episode_image")


def valid_artwork(value: object) -> str:
    """Accept remote HTTP(S) and explicitly selected absolute local files."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > 8192:
        return ""
    # Windows drive paths (C:\\... / C:/...) look like URL schemes to
    # urlsplit(). Check them first, otherwise Windows local artwork is
    # discarded while the identical Linux test passes.
    if value[0].isascii() and value[0].isalpha() and len(value)>=3:
        if value[1]==":" and value[2] in ("\\\\","/"):
            return value if PureWindowsPath(value).is_absolute() else ""
    # M3U playlists often publish protocol-relative CDN addresses.
    if value.startswith("//"):
        value="https:"+value
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        # Broken providers sometimes supply malformed bracketed URLs.
        return ""
    if parsed.scheme in ("http", "https") and hostname:
        return value
    if parsed.scheme == "file" and parsed.path:
        return value
    if not parsed.scheme and Path(value).is_absolute():
        return value
    return ""


def pick_best_art(record: dict | None, kind: str | None = None) -> str:
    """Use cover for VOD/series, channel logo for live broadcasts."""
    if not record:
        return ""
    kind = kind or record.get("kind", "")
    keys = (CHANNEL_KEYS if kind in ("live", "football_channel") else
            SERIES_KEYS if kind == "series" else
            MOVIE_KEYS if kind == "movie" else
            ("poster_path", "logo_path", "poster", "cover", "tvg-logo",
             "logo", "image", "stream_icon", "thumb"))
    # M3U keys are case-insensitive, including hyphenated properties.
    cleaned = {str(key).lower(): val for key, val in record.items()}
    for key in keys:
        image = valid_artwork(cleaned.get(key))
        if image:
            return image
    return ""


def image_cache_file(directory: Path, url: str) -> Path:
    """Hash even credential-bearing image URLs; never expose query secrets."""
    return directory / (sha256(url.encode("utf-8")).hexdigest() + ".img")


def xtream_stream_id(url: str, kind: str) -> str:
    """Match exact Xtream stream identifiers; never guess by title."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    path = unquote(parsed.path).strip("/")
    segments = path.split("/")
    directory = "live" if kind == "live" else "movie" if kind == "movie" else ""
    # /live/username/password/123.ts or /movie/username/password/123.mp4
    if not directory or len(segments) != 4 or segments[0].lower() != directory:
        return ""
    token = segments[-1].split(".", 1)[0]
    return token if token.isascii() and token.isdecimal() else ""
