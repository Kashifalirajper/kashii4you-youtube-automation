"""Make generated Shorts meaningfully original before upload."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..config import AutomationConfig


@dataclass
class TransformationResult:
    file_path: str
    transformation_applied: bool
    synthetic_media_used: bool
    script: str


def generate_original_script(source_transcript: Dict, highlight: Dict, topic_context: Optional[Dict] = None) -> str:
    topic = (topic_context or {}).get("title") or highlight.get("title") or "this topic"
    hook = highlight.get("hook_sentence") or "Here is the key moment."
    reason = highlight.get("virality_reason") or "It is useful context for viewers."
    return (
        f"Quick context: this Short is about {topic}. "
        f"{hook} "
        f"My takeaway: {reason} "
        "Watch for the main idea, not just the clip."
    )


def generate_title_description_tags(result: Dict, trend_context: Dict, config: AutomationConfig) -> Dict:
    base_title = str(result.get("title") or trend_context.get("title") or "AI-assisted Short").strip()
    niche = str(trend_context.get("niche") or "").replace("_", " ").strip()
    channel_name = config.channel_name or "Kashii4you"
    title = base_title[:96].rstrip() or "Islamic Reminder"
    if "#Shorts" not in title and len(title) <= 92:
        title = f"{title} #Shorts"

    source_url = trend_context.get("url", "")
    seo_topic = niche.title() if niche else "Islamic Reminder"
    hashtags = [
        "#Shorts",
        "#IslamicShorts",
        "#IslamicReminder",
        "#Muslim",
        "#Dua",
        "#Sabr",
        "#Allah",
    ]
    description_lines = [
        f"{title}",
        "",
        f"A calm {seo_topic} short from {channel_name}.",
        "Original reminder, premium edit, and peaceful background audio for daily motivation.",
        "",
        "Subscribe for daily Islamic reminders, duas, sabr motivation, and short faith-based reflections.",
    ]
    if source_url:
        description_lines.append(f"Source/context: {source_url}")
    description_lines.extend(["", " ".join(hashtags)])

    seo_tags = [
        *(config.default_tags or []),
        "shorts",
        "youtube shorts",
        "islamic shorts",
        "islamic reminder",
        "islamic motivation",
        "muslim motivation",
        "daily islamic reminder",
        "dua",
        "sabr",
        "allah",
        "astaghfirullah",
        "islamic quotes",
        "urdu islamic status",
        "hindi islamic status",
        "kashii4you",
    ]
    if niche:
        seo_tags.append(niche)
    tags: List[str] = list(dict.fromkeys(seo_tags))
    for tag in trend_context.get("tags", []) or []:
        if len(tags) >= 15:
            break
        tag_text = str(tag).strip()
        if tag_text:
            tags.append(tag_text[:30])

    return {
        "title": title[:100],
        "description": "\n".join(description_lines),
        "tags": list(dict.fromkeys(tags))[:15],
        "category_id": config.default_category_id,
        "contains_synthetic_media": True,
    }


def create_voiceover(script: str) -> Optional[str]:
    """Stub for future TTS provider integration."""
    return None


def _escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def apply_commentary_overlay(
    file_path: str,
    script: str,
    output_path: Optional[str] = None,
    brand_name: str = "",
) -> TransformationResult:
    source = Path(file_path)
    output = Path(output_path) if output_path else source.with_name(f"{source.stem}_transformed{source.suffix}")
    overlay = script[:140]
    if brand_name:
        overlay = f"{brand_name}: {overlay}"
    overlay = _escape_drawtext(overlay)
    vf = (
        "drawbox=x=0:y=ih-180:w=iw:h=180:color=black@0.55:t=fill,"
        f"drawtext=text='{overlay}':x=40:y=h-145:w=w-80:fontcolor=white:fontsize=34:"
        "box=0:line_spacing=8"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        str(output),
    ]
    subprocess.run(cmd, check=True)
    return TransformationResult(
        file_path=str(output),
        transformation_applied=os.path.exists(output),
        synthetic_media_used=True,
        script=script,
    )


def ensure_transformation(file_path: str, transcript: Dict, highlight: Dict, trend_context: Dict, config: AutomationConfig) -> TransformationResult:
    script = generate_original_script(transcript, highlight, trend_context)
    return apply_commentary_overlay(file_path, script, brand_name=config.brand_name)
