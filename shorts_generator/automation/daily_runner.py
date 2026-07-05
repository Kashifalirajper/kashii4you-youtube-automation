"""Daily safe Shorts automation pipeline."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..compliance.source_policy import HIGH_RISK_TERMS, is_source_allowed
from ..config import AutomationConfig, load_automation_config
from ..discovery.scoring import calculate_trend_score, reject_reason
from ..discovery.youtube_trends import get_trending_videos, search_trending_by_keywords
from ..pipeline import generate_shorts
from ..storage.db import AutomationDB
from ..transform.originalize import ensure_transformation, generate_title_description_tags
from ..transform.original_video import choose_niche_topic, generate_original_topic_short
from ..upload.youtube_uploader import upload_short

LOGGER = logging.getLogger(__name__)


def _write_latest_summary(summary: Dict, config: Optional[AutomationConfig] = None) -> None:
    logs_dir = Path(config.logs_dir if config else "logs")
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "latest_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def discover_candidates(region: str, max_results: int, config: AutomationConfig) -> List[Dict]:
    candidates = get_trending_videos(region_code=region, max_results=max_results, config=config)
    if config.topic_keywords:
        candidates.extend(
            search_trending_by_keywords(config.topic_keywords, region_code=region, max_results=max_results, config=config)
        )
    unique: Dict[str, Dict] = {}
    for video in candidates:
        unique[video["video_id"]] = video
    return list(unique.values())


def score_and_filter(candidates: List[Dict], config: AutomationConfig, db: AutomationDB, force: bool = False) -> Dict:
    accepted: List[Dict] = []
    rejected: List[Dict] = []
    for video in candidates:
        if not force and db.source_processed(video.get("video_id", "")):
            rejected.append({"video": video, "reason": "already processed"})
            continue
        reason = reject_reason(video, config)
        score, parts = calculate_trend_score(video, config)
        decision = is_source_allowed(video, config)
        video["_trend_score"] = score
        video["_score_parts"] = parts
        video["_compliance"] = decision.to_dict()
        if reason:
            rejected.append({"video": video, "reason": reason})
            db.record_source(video, score, "rejected", decision.to_dict())
            continue
        accepted.append(video)
    accepted.sort(key=lambda item: int(item.get("_trend_score", 0)), reverse=True)
    return {"accepted": accepted, "rejected": rejected}


def _short_duration(short: Dict) -> float:
    return float(short.get("end_time", 0.0)) - float(short.get("start_time", 0.0))


def _safe_original_topic(candidate: Dict, config: AutomationConfig) -> bool:
    text = " ".join(
        [
            str(candidate.get("title", "")),
            str(candidate.get("description", "")),
            " ".join(str(tag) for tag in candidate.get("tags", []) or []),
        ]
    ).lower()
    if str(candidate.get("category_id", "")) == "10":
        return False
    if any(term in text for term in HIGH_RISK_TERMS):
        return False
    return not any(keyword.lower() in text for keyword in config.excluded_keywords)


def _niche_seed(config: AutomationConfig) -> str:
    now = datetime.now(timezone.utc)
    interval = max(1, int(config.upload_interval_hours))
    slot = now.hour // interval
    return f"{now:%Y%m%d}-{slot}"


def run_once(
    region: str = "US",
    mode: str = "local",
    max_uploads: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    config_path: str = "config/automation.yaml",
) -> Dict:
    config = load_automation_config(config_path)
    max_uploads = max_uploads if max_uploads is not None else config.daily_max_uploads
    db = AutomationDB(config.database_path)
    run_id = str(uuid.uuid4())
    summary = {
        "run_id": run_id,
        "candidates_discovered": 0,
        "rejected": [],
        "shorts_generated": 0,
        "uploads_completed": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    if dry_run:
        topic = choose_niche_topic(config, seed=_niche_seed(config))
        summary["original_niche_candidate"] = {
            "niche": topic.get("niche"),
            "title": topic.get("title"),
            "mode": "would generate fully original niche short",
        }
        _write_latest_summary(summary, config)
        return summary

    if not dry_run:
        topic = choose_niche_topic(config, seed=_niche_seed(config))
        topic_video_id = f"topic-{topic['video_id']}"
        if force or not db.source_processed(topic_video_id):
            try:
                original = generate_original_topic_short(topic, config, out_dir=config.output_dir)
                metadata = generate_title_description_tags(
                    {"title": f"{topic['title']} #Shorts"},
                    {**topic, "url": ""},
                    config,
                )
                metadata["description"] = (
                    f"Original {topic.get('niche', 'educational')} Short by {config.channel_name or 'Kashii4you'}.\n"
                    "AI-assisted editing/commentary. No reused creator footage.\n#Shorts"
                )
                source_id = db.record_source(
                    {**topic, "video_id": topic_video_id, "url": "", "channel_id": "original"},
                    100,
                    "original_niche",
                    {
                        "allowed": True,
                        "reason": "Fully original niche Short generated without reused creator footage.",
                        "risk_level": "low",
                        "requires_manual_review": False,
                        "permission_basis": "original",
                    },
                )
                generated_id = db.record_short(
                    source_id,
                    original["file_path"],
                    metadata["title"],
                    100,
                    bool(original["transformation_applied"]),
                    "low",
                    metadata,
                )
                upload_result = upload_short(
                    original["file_path"],
                    metadata,
                    privacy_status=config.default_upload_privacy,
                    config=config,
                    compliance={"allowed": True, "risk_level": "low"},
                    transformation_applied=bool(original["transformation_applied"]),
                    duration_seconds=float(original["duration_seconds"]),
                )
                db.record_upload(generated_id, original["file_path"], upload_result)
                summary["shorts_generated"] = 1
                summary["uploads_completed"] = 1
                summary["original_niche_upload"] = upload_result
                summary["niche"] = topic.get("niche")
                summary["voiceover_applied"] = bool(original.get("voiceover_applied"))
                _write_latest_summary(summary, config)
                return summary
            except Exception as e:
                message = f"original niche generation/upload failed: {e}"
                db.log(run_id, "error", message)
                summary["errors"].append(message)
                _write_latest_summary(summary, config)
                return summary

    try:
        candidates = discover_candidates(region, config.daily_max_source_videos, config)
        summary["candidates_discovered"] = len(candidates)
        db.log(run_id, "info", f"discovered {len(candidates)} candidates")
    except Exception as e:
        message = f"discovery failed safely: {e}"
        db.log(run_id, "error", message)
        summary["errors"].append(message)
        _write_latest_summary(summary, config)
        return summary

    filtered = score_and_filter(candidates, config, db, force=force)
    summary["rejected"] = [
        {"video_id": item["video"].get("video_id"), "title": item["video"].get("title"), "reason": item["reason"]}
        for item in filtered["rejected"]
    ]
    for item in summary["rejected"]:
        db.log(run_id, "info", f"rejected {item['video_id']}: {item['reason']}")

    selected = filtered["accepted"][:max_uploads]
    if dry_run:
        db.log(run_id, "info", f"dry run selected {len(selected)} candidates and uploaded nothing")
        summary["selected"] = [
            {"video_id": item.get("video_id"), "title": item.get("title"), "score": item.get("_trend_score")}
            for item in selected
        ]
        if not selected and candidates:
            topic = candidates[0]
            summary["original_topic_candidate"] = {
                "video_id": topic.get("video_id"),
                "title": topic.get("title"),
                "mode": "would generate original stock/topic short",
            }
        return summary

    if not selected and candidates:
        topic = next(
            (
                candidate for candidate in candidates
                if not db.source_processed(f"topic-{candidate.get('video_id', '')}")
                and _safe_original_topic(candidate, config)
            ),
            None,
        )
        if topic is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H")
            topic = {
                "video_id": f"creator-tip-{stamp}",
                "title": "Daily creator productivity tip",
                "description": "Original channel-safe creator education topic.",
                "tags": ["creator", "productivity", "shorts"],
                "category_id": config.default_category_id,
                "_trend_score": 70,
            }
            if db.source_processed(f"topic-{topic['video_id']}"):
                db.log(run_id, "info", "fallback original topic already processed this period")
                return summary
        try:
            original = generate_original_topic_short(topic, config, out_dir=config.output_dir)
            metadata = generate_title_description_tags(
                {"title": f"{config.channel_name or 'Kashii4you'} Trend Brief #Shorts"},
                {**topic, "url": ""},
                config,
            )
            metadata["description"] = (
                "Original AI-assisted trend commentary/editing. "
                "Trend source used for topic discovery only.\n#Shorts"
            )
            source_id = db.record_source(
                {
                    **topic,
                    "video_id": f"topic-{topic.get('video_id', run_id)}",
                    "url": "",
                    "channel_id": "original",
                },
                int(topic.get("_trend_score", 0) or 0),
                "original_topic",
                {
                    "allowed": True,
                    "reason": "Original topic-only video generated from trend context.",
                    "risk_level": "low",
                    "requires_manual_review": False,
                    "permission_basis": "original",
                },
            )
            generated_id = db.record_short(
                source_id,
                original["file_path"],
                metadata["title"],
                int(topic.get("_trend_score", 0) or 0),
                bool(original["transformation_applied"]),
                "low",
                metadata,
            )
            upload_result = upload_short(
                original["file_path"],
                metadata,
                privacy_status=config.default_upload_privacy,
                config=config,
                compliance={"allowed": True, "risk_level": "low"},
                transformation_applied=bool(original["transformation_applied"]),
                duration_seconds=float(original["duration_seconds"]),
            )
            db.record_upload(generated_id, original["file_path"], upload_result)
            summary["shorts_generated"] += 1
            summary["uploads_completed"] += 1
            summary["original_topic_upload"] = upload_result
            return summary
        except Exception as e:
            message = f"original topic generation/upload failed: {e}"
            db.log(run_id, "error", message)
            summary["errors"].append(message)
            return summary

    for video in selected:
        try:
            decision = video["_compliance"]
            source_id = db.record_source(video, int(video.get("_trend_score", 0)), "allowed", decision)
            result = generate_shorts(
                video["url"],
                num_clips=1,
                aspect_ratio="9:16",
                download_format="720",
                language=config.default_language,
                mode=mode,
            )
            output_dir = Path(config.output_dir)
            output_dir.mkdir(exist_ok=True)
            json_path = output_dir / f"automation_{video['video_id']}.json"
            json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

            for short in result.get("shorts", [])[:1]:
                duration = _short_duration(short)
                if duration > config.short_max_duration_seconds:
                    raise RuntimeError(f"generated short exceeds {config.short_max_duration_seconds}s")
                source_path = short.get("clip_url")
                if not source_path:
                    raise RuntimeError(f"short generation failed: {short.get('error')}")
                transformed = ensure_transformation(source_path, result.get("transcript", {}), short, video, config)
                if config.transformation_required and not transformed.transformation_applied:
                    raise RuntimeError("transformation required but not applied")
                metadata = generate_title_description_tags(short, video, config)
                generated_id = db.record_short(
                    source_id,
                    transformed.file_path,
                    metadata["title"],
                    int(short.get("score", 0) or 0),
                    transformed.transformation_applied,
                    str(decision.get("risk_level", "high")),
                    metadata,
                )
                privacy = config.default_upload_privacy
                upload_result = upload_short(
                    transformed.file_path,
                    metadata,
                    privacy_status=privacy,
                    config=config,
                    compliance=decision,
                    transformation_applied=transformed.transformation_applied,
                    duration_seconds=duration,
                )
                db.record_upload(generated_id, transformed.file_path, upload_result)
                summary["shorts_generated"] += 1
                summary["uploads_completed"] += 1
        except Exception as e:
            message = f"{video.get('video_id')}: {e}"
            db.log(run_id, "error", message)
            summary["errors"].append(message)

    _write_latest_summary(summary, config)
    return summary
