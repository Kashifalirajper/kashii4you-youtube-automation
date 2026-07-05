import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

MUAPI_API_KEY = os.getenv("MUAPI_API_KEY", "").strip()
MUAPI_BASE_URL = os.getenv("MUAPI_BASE_URL", "https://api.muapi.ai/api/v1").rstrip("/")

POLL_INTERVAL_SECONDS = float(os.getenv("MUAPI_POLL_INTERVAL", "5"))
POLL_TIMEOUT_SECONDS = float(os.getenv("MUAPI_POLL_TIMEOUT", "600"))

# Local-mode (--mode local) settings — only consulted when running offline.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LOCAL_WHISPER_MODEL = os.getenv("LOCAL_WHISPER_MODEL", "base")
LOCAL_WHISPER_DEVICE = os.getenv("LOCAL_WHISPER_DEVICE", "auto")  # auto / cpu / cuda
LOCAL_OUTPUT_DIR = os.getenv("LOCAL_OUTPUT_DIR", "output")

# VAD (Voice Activity Detection) settings for faster-whisper
# Default threshold is 0.5; lower = more sensitive, higher = less sensitive
# Default min_speech_duration_ms is 250ms; increase to avoid tiny false positives
# Default min_silence_duration_ms is 2000ms; increase to avoid splitting mid-sentence
# DISABLED by default because VAD is too aggressive on mixed speech/music content
LOCAL_WHISPER_VAD_FILTER = os.getenv("LOCAL_WHISPER_VAD_FILTER", "false").strip().lower() == "true"
_vad_params_env = os.getenv("LOCAL_WHISPER_VAD_PARAMETERS", "")
if _vad_params_env:
    import json
    LOCAL_WHISPER_VAD_PARAMETERS = json.loads(_vad_params_env)
else:
    # Match faster-whisper defaults when VAD is enabled
    LOCAL_WHISPER_VAD_PARAMETERS = {
        "threshold": 0.5,
        "min_speech_duration_ms": 250,
        "max_speech_duration_s": float("inf"),
        "min_silence_duration_ms": 2000,
        "speech_pad_ms": 400,
    }


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class ComplianceConfig:
    require_permission: bool = True
    allow_creative_commons: bool = True
    allow_public_standard_license_without_permission: bool = False
    require_ai_voiceover_or_commentary: bool = True
    max_clip_duration_seconds: int = 58
    upload_privacy_before_review: str = "private"


@dataclass
class UploadSchedule:
    enabled: bool = True
    hour: int = 10
    minute: int = 0


@dataclass
class AutomationConfig:
    channel_name: str = ""
    youtube_api_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_token_base64: str = ""
    youtube_client_secrets_file: str = "client_secrets.json"
    youtube_oauth_token_file: str = "token.json"
    pexels_api_key: str = ""
    unsplash_access_key: str = ""
    upload_interval_hours: int = 8
    upload_times: List[str] = field(default_factory=lambda: ["08:00", "14:00", "20:00"])
    watermark_text: str = ""
    content_niches: List[str] = field(default_factory=lambda: ["islamic_facts", "urdu_hindi_motivation", "tech_tips", "ai_tools", "kids_educational"])
    licensed_audio_dir: str = "assets/audio"
    brand_font_file: str = ""
    voiceover_enabled: bool = False
    visual_preset: str = "premium_islamic_short"
    auto_publish: bool = False
    default_upload_privacy: str = "private"
    daily_max_uploads: int = 1
    daily_max_source_videos: int = 10
    min_trend_score: int = 70
    short_max_duration_seconds: int = 58
    allowed_source_policy: str = "strict"
    transformation_required: bool = True
    brand_name: str = ""
    default_language: str = "en"
    timezone: str = "Asia/Karachi"
    automation_mode: str = "local"
    output_dir: str = "output"
    logs_dir: str = "logs"
    database_path: str = "automation.sqlite"
    max_source_duration_seconds: Optional[int] = None
    made_for_kids: bool = False
    allowed_channel_ids: List[str] = field(default_factory=list)
    blocked_channel_ids: List[str] = field(default_factory=list)
    allowed_source_urls: List[str] = field(default_factory=list)
    topic_keywords: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    default_category_id: str = "22"
    default_tags: List[str] = field(default_factory=lambda: ["shorts"])
    upload_schedule: UploadSchedule = field(default_factory=UploadSchedule)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise RuntimeError("pyyaml is required for automation config. Install requirements.txt.") from e
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Automation config must be a mapping: {path}")
    return data


def load_automation_config(config_path: str = "config/automation.yaml") -> AutomationConfig:
    data = _load_yaml_file(Path(config_path))
    compliance_data = data.get("compliance") or {}
    schedule_data = data.get("upload_schedule") or {}

    config = AutomationConfig(
        channel_name=os.getenv("CHANNEL_NAME", "").strip(),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
        youtube_client_id=os.getenv("YOUTUBE_CLIENT_ID", "").strip(),
        youtube_client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", "").strip(),
        youtube_token_base64=os.getenv("YOUTUBE_TOKEN_BASE64", "").strip(),
        youtube_client_secrets_file=os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json").strip(),
        youtube_oauth_token_file=os.getenv("YOUTUBE_OAUTH_TOKEN_FILE", "token.json").strip(),
        pexels_api_key=os.getenv("PEXELS_API_KEY", "").strip(),
        unsplash_access_key=os.getenv("UNSPLASH_ACCESS_KEY", "").strip(),
        upload_interval_hours=_env_int("UPLOAD_INTERVAL_HOURS", 8),
        upload_times=[
            item.strip().strip('"').strip("'")
            for item in os.getenv("UPLOAD_TIMES", "08:00,14:00,20:00").replace('"', "").split(",")
            if item.strip()
        ],
        watermark_text=os.getenv("WATERMARK_TEXT", "").strip().strip('"'),
        licensed_audio_dir=os.getenv("LICENSED_AUDIO_DIR", "assets/audio").strip() or "assets/audio",
        brand_font_file=os.getenv("BRAND_FONT_FILE", "").strip(),
        voiceover_enabled=_env_bool("VOICEOVER_ENABLED", False),
        visual_preset=os.getenv("VISUAL_PRESET", "premium_islamic_short").strip() or "premium_islamic_short",
        content_niches=[
            item.strip()
            for item in os.getenv(
                "CONTENT_NICHES",
                "islamic_facts,urdu_hindi_motivation,tech_tips,ai_tools,kids_educational",
            ).split(",")
            if item.strip()
        ],
        auto_publish=_env_bool("AUTO_PUBLISH", False),
        default_upload_privacy=os.getenv("DEFAULT_UPLOAD_PRIVACY", "private").strip() or "private",
        daily_max_uploads=_env_int("DAILY_MAX_UPLOADS", 1),
        daily_max_source_videos=_env_int("DAILY_MAX_SOURCE_VIDEOS", 10),
        min_trend_score=_env_int("MIN_TREND_SCORE", 70),
        short_max_duration_seconds=_env_int("SHORT_MAX_DURATION_SECONDS", 58),
        allowed_source_policy=os.getenv("ALLOWED_SOURCE_POLICY", "strict").strip().lower() or "strict",
        transformation_required=_env_bool("TRANSFORMATION_REQUIRED", True),
        brand_name=os.getenv("BRAND_NAME", "").strip(),
        default_language=os.getenv("DEFAULT_LANGUAGE", "en").strip() or "en",
        timezone=os.getenv("TIMEZONE", "Asia/Karachi").strip() or "Asia/Karachi",
        automation_mode=os.getenv("AUTOMATION_MODE", "local").strip().lower() or "local",
        output_dir=os.getenv("OUTPUT_DIR", os.getenv("LOCAL_OUTPUT_DIR", "output")).strip() or "output",
        logs_dir=os.getenv("LOGS_DIR", "logs").strip() or "logs",
        database_path=os.getenv("AUTOMATION_DB_PATH", "automation.sqlite").strip() or "automation.sqlite",
        max_source_duration_seconds=(
            _env_int("MAX_SOURCE_DURATION_SECONDS", 0) or None
        ),
        made_for_kids=_env_bool("MADE_FOR_KIDS", False),
        allowed_channel_ids=list(data.get("allowed_channel_ids") or []),
        blocked_channel_ids=list(data.get("blocked_channel_ids") or []),
        allowed_source_urls=list(data.get("allowed_source_urls") or []),
        topic_keywords=list(data.get("topic_keywords") or []),
        excluded_keywords=list(data.get("excluded_keywords") or []),
        default_category_id=str(data.get("default_category_id") or "22"),
        default_tags=list(data.get("default_tags") or ["shorts"]),
        upload_schedule=UploadSchedule(
            enabled=bool(schedule_data.get("enabled", True)),
            hour=int(schedule_data.get("hour", 10)),
            minute=int(schedule_data.get("minute", 0)),
        ),
        compliance=ComplianceConfig(
            require_permission=bool(compliance_data.get("require_permission", True)),
            allow_creative_commons=bool(compliance_data.get("allow_creative_commons", True)),
            allow_public_standard_license_without_permission=bool(
                compliance_data.get("allow_public_standard_license_without_permission", False)
            ),
            require_ai_voiceover_or_commentary=bool(
                compliance_data.get("require_ai_voiceover_or_commentary", True)
            ),
            max_clip_duration_seconds=int(compliance_data.get("max_clip_duration_seconds", 58)),
            upload_privacy_before_review=str(compliance_data.get("upload_privacy_before_review", "private")),
        ),
    )
    return config


def require_api_key() -> str:
    if not MUAPI_API_KEY:
        raise RuntimeError(
            "MUAPI_API_KEY is not set. Add it to your .env file or export it as an env var."
        )
    return MUAPI_API_KEY


def require_openai_key() -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Local mode needs an OpenAI key for highlight ranking. "
            "Add it to your .env or export it, or switch back to --mode api."
        )
    return OPENAI_API_KEY


def require_gemini_key() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Local mode needs a Gemini key when LLM_PROVIDER=gemini. "
            "Add it to your .env or export it, or switch LLM_PROVIDER back to openai."
        )
    return GEMINI_API_KEY
