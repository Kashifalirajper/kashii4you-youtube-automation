"""Optional stock media search helpers for original/owned B-roll."""
from __future__ import annotations

from typing import Dict, List

import requests

from ..config import AutomationConfig


def search_pexels_videos(query: str, config: AutomationConfig, per_page: int = 5) -> List[Dict]:
    if not config.pexels_api_key:
        return []
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": config.pexels_api_key},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("videos", [])


def search_unsplash_photos(query: str, config: AutomationConfig, per_page: int = 5) -> List[Dict]:
    if not config.unsplash_access_key:
        return []
    response = requests.get(
        "https://api.unsplash.com/search/photos",
        headers={"Authorization": f"Client-ID {config.unsplash_access_key}"},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def find_stock_context(query: str, config: AutomationConfig) -> Dict:
    return {
        "pexels_videos": search_pexels_videos(query, config),
        "unsplash_photos": search_unsplash_photos(query, config),
    }
