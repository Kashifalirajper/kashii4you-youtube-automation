"""Hard source permission gates."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Dict, Literal

from ..config import AutomationConfig

LOGGER = logging.getLogger(__name__)
RiskLevel = Literal["low", "medium", "high"]
PermissionBasis = Literal["own_channel", "whitelist", "creative_commons", "explicit_permission", "rejected"]

HIGH_RISK_TERMS = {
    "official music video",
    "lyrics",
    "movie clip",
    "trailer",
    "tv show",
    "full match",
    "highlights",
    "podcast",
    "interview",
    "celebrity",
    "nba",
    "nfl",
    "fifa",
    "ufc",
}


@dataclass
class ComplianceDecision:
    allowed: bool
    reason: str
    risk_level: RiskLevel
    requires_manual_review: bool
    permission_basis: PermissionBasis

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _text(video: Dict) -> str:
    return " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(str(tag) for tag in video.get("tags", []) or []),
        ]
    ).lower()


def _url_allowed(video: Dict, config: AutomationConfig) -> bool:
    url = str(video.get("url", "")).strip()
    return any(url == allowed or (allowed and allowed in url) for allowed in config.allowed_source_urls)


def is_source_allowed(video: Dict, config: AutomationConfig) -> ComplianceDecision:
    channel_id = str(video.get("channel_id", ""))
    video_text = _text(video)

    if channel_id in config.blocked_channel_ids:
        decision = ComplianceDecision(False, "Channel is blocked.", "high", False, "rejected")
        LOGGER.info("compliance rejected %s: %s", video.get("video_id"), decision.reason)
        return decision

    for keyword in config.excluded_keywords:
        if keyword.lower() in video_text:
            decision = ComplianceDecision(False, f"Matched excluded keyword: {keyword}", "high", False, "rejected")
            LOGGER.info("compliance rejected %s: %s", video.get("video_id"), decision.reason)
            return decision

    if any(term in video_text for term in HIGH_RISK_TERMS) and channel_id not in config.allowed_channel_ids:
        decision = ComplianceDecision(
            False,
            "Likely high-risk copyrighted category without whitelist permission.",
            "high",
            False,
            "rejected",
        )
        LOGGER.info("compliance rejected %s: %s", video.get("video_id"), decision.reason)
        return decision

    if channel_id in config.allowed_channel_ids:
        decision = ComplianceDecision(True, "Channel is explicitly allowed.", "low", False, "whitelist")
        LOGGER.info("compliance allowed %s: %s", video.get("video_id"), decision.reason)
        return decision

    if _url_allowed(video, config):
        decision = ComplianceDecision(True, "URL is explicitly marked permission_granted in config.", "low", False, "explicit_permission")
        LOGGER.info("compliance allowed %s: %s", video.get("video_id"), decision.reason)
        return decision

    if str(video.get("license", "")).lower() == "creativecommon":
        if config.compliance.allow_creative_commons:
            decision = ComplianceDecision(True, "Creative Commons license allowed by config.", "medium", True, "creative_commons")
        else:
            decision = ComplianceDecision(False, "Creative Commons sources are disabled by config.", "high", False, "rejected")
        LOGGER.info("compliance decision %s: %s", video.get("video_id"), decision.reason)
        return decision

    if config.compliance.allow_public_standard_license_without_permission:
        decision = ComplianceDecision(
            True,
            "Standard license allowed by config but requires manual review.",
            "medium",
            True,
            "explicit_permission",
        )
        LOGGER.info("compliance allowed with review %s: %s", video.get("video_id"), decision.reason)
        return decision

    decision = ComplianceDecision(
        False,
        "No permission basis for standard public YouTube source.",
        "high",
        False,
        "rejected",
    )
    LOGGER.info("compliance rejected %s: %s", video.get("video_id"), decision.reason)
    return decision
