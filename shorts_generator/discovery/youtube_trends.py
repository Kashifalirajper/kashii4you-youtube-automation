"""YouTube Data API trend discovery."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

import isodate
import requests

from ..config import AutomationConfig, load_automation_config

LOGGER = logging.getLogger(__name__)
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _api_get(path: str, params: Dict[str, object], config: AutomationConfig) -> Dict:
    if not config.youtube_api_key:
        return _oauth_get(path, params, config)
    merged = {**params, "key": config.youtube_api_key}
    response = requests.get(f"{YOUTUBE_API_BASE}/{path}", params=merged, timeout=30)
    if response.status_code >= 400:
        LOGGER.error("YouTube API failed: %s %s", response.status_code, response.text[:500])
        raise RuntimeError(f"YouTube API failed with status {response.status_code}.")
    return response.json()


def _oauth_get(path: str, params: Dict[str, object], config: AutomationConfig) -> Dict:
    try:
        from ..upload.youtube_uploader import get_authenticated_service
    except Exception as e:
        raise RuntimeError("YOUTUBE_API_KEY is not set and OAuth fallback is unavailable.") from e

    youtube = get_authenticated_service(config)
    if path == "videos":
        return youtube.videos().list(**params).execute()
    if path == "search":
        return youtube.search().list(**params).execute()
    raise RuntimeError(f"Unsupported YouTube API path for OAuth fallback: {path}")


def _duration_seconds(value: str) -> int:
    try:
        return int(isodate.parse_duration(value).total_seconds())
    except Exception:
        return 0


def _int_stat(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_video(item: Dict) -> Dict:
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    statistics = item.get("statistics") or {}
    status = item.get("status") or {}
    video_id = item.get("id")
    if isinstance(video_id, dict):
        video_id = video_id.get("videoId")
    video_id = str(video_id or "")
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration_seconds": _duration_seconds(content.get("duration", "")),
        "view_count": _int_stat(statistics.get("viewCount")),
        "like_count": _int_stat(statistics.get("likeCount")),
        "comment_count": _int_stat(statistics.get("commentCount")),
        "tags": snippet.get("tags", []) or [],
        "licensed_content": bool(content.get("licensedContent", False)),
        "license": status.get("license", ""),
        "category_id": snippet.get("categoryId", ""),
    }


def get_video_details(video_ids: Iterable[str], config: Optional[AutomationConfig] = None) -> List[Dict]:
    config = config or load_automation_config()
    ids = [video_id for video_id in video_ids if video_id]
    if not ids:
        return []
    videos: List[Dict] = []
    for i in range(0, len(ids), 50):
        data = _api_get(
            "videos",
            {
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(ids[i : i + 50]),
                "maxResults": 50,
            },
            config,
        )
        videos.extend(normalize_video(item) for item in data.get("items", []))
    return videos


def get_trending_videos(
    region_code: str = "US",
    category_id: Optional[str] = None,
    max_results: int = 25,
    config: Optional[AutomationConfig] = None,
) -> List[Dict]:
    config = config or load_automation_config()
    params: Dict[str, object] = {
        "part": "snippet,contentDetails,statistics,status",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": min(max_results, 50),
    }
    if category_id:
        params["videoCategoryId"] = category_id
    data = _api_get("videos", params, config)
    return [normalize_video(item) for item in data.get("items", [])]


def search_trending_by_keywords(
    keywords: Iterable[str],
    region_code: str = "US",
    max_results: int = 25,
    config: Optional[AutomationConfig] = None,
) -> List[Dict]:
    config = config or load_automation_config()
    video_ids: List[str] = []
    per_keyword = max(1, min(25, max_results))
    for keyword in keywords:
        data = _api_get(
            "search",
            {
                "part": "snippet",
                "type": "video",
                "q": keyword,
                "regionCode": region_code,
                "order": "viewCount",
                "maxResults": per_keyword,
            },
            config,
        )
        for item in data.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)
            if len(video_ids) >= max_results:
                break
    return get_video_details(video_ids[:max_results], config=config)
