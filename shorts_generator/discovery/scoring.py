"""Trend scoring for candidate source videos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple

from ..compliance.source_policy import is_source_allowed
from ..config import AutomationConfig


def _parse_published_at(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _keyword_text(video: Dict) -> str:
    return " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(str(tag) for tag in video.get("tags", []) or []),
        ]
    ).lower()


def calculate_trend_score(video: Dict, config: AutomationConfig) -> Tuple[int, Dict[str, int]]:
    published = _parse_published_at(str(video.get("published_at", "")))
    age_hours = max(1.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
    views = int(video.get("view_count", 0) or 0)
    likes = int(video.get("like_count", 0) or 0)
    comments = int(video.get("comment_count", 0) or 0)
    views_per_hour = views / age_hours

    velocity_score = min(30, int(views_per_hour / 1000 * 30))
    engagement_rate = (likes + comments * 2) / max(views, 1)
    engagement_score = min(25, int(engagement_rate * 1000))
    freshness_score = max(0, min(20, int(20 - age_hours / 24)))

    text = _keyword_text(video)
    topic_hits = sum(1 for keyword in config.topic_keywords if keyword.lower() in text)
    topic_score = 15 if not config.topic_keywords else min(15, topic_hits * 5)

    decision = is_source_allowed(video, config)
    safety_score = 10 if decision.allowed and decision.risk_level == "low" else 5 if decision.allowed else 0

    parts = {
        "velocity": velocity_score,
        "engagement": engagement_score,
        "freshness": freshness_score,
        "topic": topic_score,
        "safety": safety_score,
    }
    return min(100, sum(parts.values())), parts


def reject_reason(video: Dict, config: AutomationConfig) -> str:
    text = _keyword_text(video)
    if str(video.get("channel_id", "")) in config.blocked_channel_ids:
        return "blocked channel"
    for keyword in config.excluded_keywords:
        if keyword.lower() in text:
            return f"excluded keyword: {keyword}"
    if config.max_source_duration_seconds and int(video.get("duration_seconds", 0) or 0) > config.max_source_duration_seconds:
        return "source duration exceeds configured maximum"
    decision = is_source_allowed(video, config)
    if not decision.allowed:
        return decision.reason
    score, _ = calculate_trend_score(video, config)
    if score < config.min_trend_score:
        return f"trend score below threshold: {score}"
    return ""
