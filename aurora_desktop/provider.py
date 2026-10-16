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
        "User-Agent": "AURORA-IPTV-Desktop/0.4",
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
                    categories[normalized(name)] = kind
        except (requests.RequestException, ValueError, TypeError, UnicodeError):
            # A bad category API cannot disable the user's playable M3U.
            continue
    return categories
