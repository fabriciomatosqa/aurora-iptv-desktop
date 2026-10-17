"""Optional Xtream provider category metadata, mirroring ProviderApi.kt on Android.

Only connect to the same host the user entered. Never send playlist credentials
to a discovery service, search engine or third-party metadata proxy.
"""
from __future__ import annotations

import json
import requests

from .android_rules import normalized, provider_api_endpoint

CATEGORY_ACTIONS = (
    ("get_live_categories", "live"),
    ("get_vod_categories", "movie"),
    ("get_series_categories", "series"),
)


def _read_small_json(url: str, maximum: int = 4 * 1024 * 1024):
    with requests.get(url, stream=True, timeout=(8, 16), headers={
        "Accept": "application/json", "Accept-Encoding": "gzip",
        "User-Agent": "AURORA-IPTV-Desktop/0.5",
    }) as resp:
        resp.raise_for_status()
        size = 0
        chunks = []
        for chunk in resp.iter_content(64 * 1024):
            size += len(chunk)
            if size > maximum:
                raise ValueError("Metadata exceeds the safe download limit")
            chunks.append(chunk)
        return json.loads(b"".join(chunks).decode("utf-8-sig"))


def get_provider_category_kinds(source: str) -> dict[str, str]:
    """Use official category types, falling back without changing existing data."""
    if provider_api_endpoint(source, "get_live_categories") is None:
        return {}
    categories = {}
    ambiguous = set()
    for action, kind in CATEGORY_ACTIONS:
        url = provider_api_endpoint(source, action)
        if not url:
            continue
        try:
            rows = _read_small_json(url)
            if not isinstance(rows, list):
                continue
            for row in rows[:20_000]:
                if not isinstance(row, dict):
                    continue
                name = row.get("category_name")
                if isinstance(name, str) and name.strip():
                    key=normalized(name)
                    # One category name may occur in the live, VOD AND
                    # series endpoints. Never make last API response win:
                    # the same group label is not a reliable type signal.
                    if key in ambiguous:
                        continue
                    if key in categories and categories[key]!=kind:
                        categories.pop(key,None)
                        ambiguous.add(key)
                    else:
                        categories[key]=kind
        except (requests.RequestException, ValueError, TypeError, UnicodeError):
            # A bad category API cannot disable the user's playable M3U.
            continue
    return categories


def get_provider_series_posters(source: str) -> dict[str, str]:
    """Android ProviderApi.get_series parity: use only exact provider titles.

    Do not infer a poster from similar titles, as that leads to the wrong series.
    The response is size bounded; oversized providers still load their M3U.
    """
    url = provider_api_endpoint(source, "get_series")
    if not url:
        return {}
    try:
        rows = _read_small_json(url, maximum=18 * 1024 * 1024)
    except (requests.RequestException, ValueError, TypeError, UnicodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    posters = {}
    for row in rows[:30_000]:
        if not isinstance(row, dict):
            continue
        title, cover = row.get("name"), row.get("cover")
        if not isinstance(title,str) or not isinstance(cover,str):
            continue
        if not title.strip() or not cover.startswith(("http://", "https://")):
            continue
        posters[normalized(title)] = cover
    return posters


def get_provider_stream_artwork(source: str, kind: str) -> dict[str, str]:
    """Get exact stream-ID artwork from the user's own Xtream provider.

    No external art search, fuzzy title matching or shared credentials.
    Large provider responses are skipped rather than exhausting memory.
    """
    if kind not in ("live", "movie"):
        return {}
    action = "get_live_streams" if kind == "live" else "get_vod_streams"
    endpoint = provider_api_endpoint(source, action)
    if not endpoint:
        return {}
    try:
        rows = _read_small_json(endpoint, maximum=24 * 1024 * 1024)
    except (requests.RequestException, ValueError, TypeError, UnicodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    result = {}
    for row in rows[:90_000]:
        if not isinstance(row, dict):
            continue
        stream_id = row.get("stream_id")
        image = row.get("stream_icon") or row.get("cover") or row.get("poster") or ""
        if (str(stream_id).isascii() and str(stream_id).isdecimal()
                and isinstance(image, str) and image.startswith(("http://", "https://"))):
            result[str(stream_id)] = image
    return result
