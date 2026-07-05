"""Official YouTube Data API uploader."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import AutomationConfig, load_automation_config

YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _client_config_from_env(config: AutomationConfig) -> Optional[Dict]:
    if not config.youtube_client_id or not config.youtube_client_secret:
        return None
    return {
        "installed": {
            "client_id": config.youtube_client_id,
            "client_secret": config.youtube_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _write_token_from_base64(config: AutomationConfig, token_path: Path) -> None:
    if not config.youtube_token_base64 or token_path.exists():
        return
    raw = base64.b64decode(config.youtube_token_base64)
    try:
        parsed = json.loads(raw.decode("utf-8"))
        token_path.write_text(json.dumps(parsed), encoding="utf-8")
        return
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass

    # Some legacy deployments export a pickled google.oauth2.credentials.Credentials
    # object. Keep that conversion local and one-way so the uploader still uses
    # Google's JSON token format after startup.
    import pickle

    creds = pickle.loads(raw)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def get_authenticated_service(config: Optional[AutomationConfig] = None):
    config = config or load_automation_config()
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError("YouTube upload dependencies are missing. Install requirements.txt.") from e

    token_path = Path(config.youtube_oauth_token_file)
    _write_token_from_base64(config, token_path)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_UPLOAD_SCOPE)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        secrets = Path(config.youtube_client_secrets_file)
        client_config = _client_config_from_env(config)
        if client_config:
            flow = InstalledAppFlow.from_client_config(client_config, YOUTUBE_UPLOAD_SCOPE)
        else:
            if not secrets.exists():
                raise RuntimeError(f"OAuth client secrets file not found: {secrets}")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), YOUTUBE_UPLOAD_SCOPE)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def can_publicly_publish(
    config: AutomationConfig,
    compliance: Dict,
    transformation_applied: bool,
    duration_seconds: float,
    has_blocked_keywords: bool = False,
) -> bool:
    return (
        config.auto_publish
        and bool(compliance.get("allowed"))
        and compliance.get("risk_level") == "low"
        and transformation_applied
        and duration_seconds <= config.short_max_duration_seconds
        and not has_blocked_keywords
    )


def _privacy_for_request(config: AutomationConfig, requested: str, safe_to_publish: bool) -> str:
    requested = (requested or config.default_upload_privacy or "private").lower()
    if requested == "public" and not safe_to_publish:
        return config.default_upload_privacy if config.default_upload_privacy in {"private", "unlisted"} else "private"
    return requested if requested in {"private", "unlisted", "public"} else "private"


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(4), reraise=True)
def _execute_insert(request):
    return request.execute()


def upload_short(
    file_path: str,
    metadata: Dict,
    privacy_status: str = "private",
    publish_at: Optional[str] = None,
    config: Optional[AutomationConfig] = None,
    youtube_client=None,
    compliance: Optional[Dict] = None,
    transformation_applied: bool = True,
    duration_seconds: float = 0,
) -> Dict:
    config = config or load_automation_config()
    compliance = compliance or {"allowed": False, "risk_level": "high"}
    safe_to_publish = can_publicly_publish(config, compliance, transformation_applied, duration_seconds)
    privacy = _privacy_for_request(config, privacy_status, safe_to_publish)
    youtube = youtube_client or get_authenticated_service(config)

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        raise RuntimeError("google-api-python-client is required for upload.") from e

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": bool(config.made_for_kids),
        "containsSyntheticMedia": bool(metadata.get("contains_synthetic_media", False)),
    }
    if publish_at and privacy == "private":
        status["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "categoryId": str(metadata.get("category_id") or config.default_category_id),
        },
        "status": status,
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = _execute_insert(request)
    video_id = response.get("id", "")
    return {
        "youtube_video_id": video_id,
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "privacy_status": privacy,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
