"""Deployment environment validation."""
from __future__ import annotations

from typing import Dict, List

from ..config import AutomationConfig, load_automation_config


REQUIRED_FOR_UPLOAD = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_TOKEN_BASE64"]
OPTIONAL = ["OPENAI_API_KEY", "PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY", "MUAPI_API_KEY"]


def check_environment(config: AutomationConfig | None = None) -> Dict[str, object]:
    config = config or load_automation_config()
    values = {
        "YOUTUBE_API_KEY": config.youtube_api_key,
        "YOUTUBE_CLIENT_ID": config.youtube_client_id,
        "YOUTUBE_CLIENT_SECRET": config.youtube_client_secret,
        "YOUTUBE_TOKEN_BASE64": config.youtube_token_base64,
        "OPENAI_API_KEY": __import__("os").getenv("OPENAI_API_KEY", ""),
        "PEXELS_API_KEY": config.pexels_api_key,
        "UNSPLASH_ACCESS_KEY": config.unsplash_access_key,
        "MUAPI_API_KEY": __import__("os").getenv("MUAPI_API_KEY", ""),
    }
    missing_upload = [name for name in REQUIRED_FOR_UPLOAD if not values.get(name)]
    discovery_ready = bool(values.get("YOUTUBE_API_KEY")) or not missing_upload
    missing_required: List[str] = [*missing_upload]
    if not discovery_ready:
        missing_required.append("YOUTUBE_API_KEY or complete YouTube OAuth secrets")
    present = {name: bool(value) for name, value in values.items()}
    return {
        "ready": not missing_required,
        "discovery_auth": "api_key" if values.get("YOUTUBE_API_KEY") else "oauth" if discovery_ready else "missing",
        "missing_required": missing_required,
        "present": present,
        "safe_defaults": {
            "auto_publish": config.auto_publish,
            "default_upload_privacy": config.default_upload_privacy,
            "daily_max_uploads": config.daily_max_uploads,
            "allowed_source_policy": config.allowed_source_policy,
        },
    }
