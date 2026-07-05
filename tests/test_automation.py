from __future__ import annotations

from pathlib import Path
import base64
import json

import pytest

from shorts_generator.automation.daily_runner import run_once
from shorts_generator.automation.env_check import check_environment
from shorts_generator.compliance.source_policy import is_source_allowed
from shorts_generator.config import AutomationConfig, load_automation_config
from shorts_generator.discovery.scoring import calculate_trend_score, reject_reason
from shorts_generator.storage.db import AutomationDB
from shorts_generator.transform.originalize import generate_title_description_tags
from shorts_generator.transform.original_video import choose_niche_topic, generate_original_topic_short, _pick_licensed_audio
from shorts_generator.upload.youtube_uploader import can_publicly_publish, upload_short
from shorts_generator.upload.youtube_uploader import _write_token_from_base64


def sample_video(**overrides):
    video = {
        "video_id": "abc123",
        "url": "https://www.youtube.com/watch?v=abc123",
        "title": "Useful Python tutorial",
        "description": "A helpful educational walkthrough",
        "channel_id": "allowed-channel",
        "channel_title": "Creator",
        "published_at": "2026-07-05T00:00:00Z",
        "duration_seconds": 120,
        "view_count": 100000,
        "like_count": 5000,
        "comment_count": 500,
        "tags": ["python"],
        "license": "youtube",
    }
    video.update(overrides)
    return video


def test_trend_scoring_with_allowed_channel():
    config = AutomationConfig(allowed_channel_ids=["allowed-channel"], topic_keywords=["python"])
    score, parts = calculate_trend_score(sample_video(), config)
    assert 0 <= score <= 100
    assert parts["safety"] == 10


def test_compliance_rejects_standard_license_without_permission():
    config = AutomationConfig(allowed_channel_ids=[])
    decision = is_source_allowed(sample_video(channel_id="other"), config)
    assert not decision.allowed
    assert decision.permission_basis == "rejected"


def test_blocked_keywords_rejected():
    config = AutomationConfig(allowed_channel_ids=["allowed-channel"], excluded_keywords=["casino"])
    reason = reject_reason(sample_video(title="Casino strategy"), config)
    assert "excluded keyword" in reason


def test_duplicate_prevention(tmp_path: Path):
    db = AutomationDB(str(tmp_path / "automation.sqlite"))
    video = sample_video()
    db.record_source(video, 80, "allowed", {"allowed": True})
    assert db.source_processed("abc123")


def test_recent_uploads(tmp_path: Path):
    db = AutomationDB(str(tmp_path / "automation.sqlite"))
    db.record_upload(
        generated_short_id=1,
        file_path="output/test.mp4",
        result={"youtube_video_id": "vid123", "privacy_status": "private"},
    )
    uploads = db.recent_uploads()
    assert uploads[0]["youtube_video_id"] == "vid123"
    assert uploads[0]["privacy_status"] == "private"


def test_upload_metadata_generation_seo_description():
    config = AutomationConfig(channel_name="Kashii4you", default_tags=["shorts", "education"])
    metadata = generate_title_description_tags(
        {"title": "Allah knows what your heart carries"},
        {**sample_video(), "niche": "islamic_facts", "tags": ["dua", "sabr"]},
        config,
    )
    assert len(metadata["title"]) <= 100
    assert "daily Islamic reminders" in metadata["description"]
    assert "#IslamicShorts" in metadata["description"]
    assert "islamic reminder" in metadata["tags"]
    assert "dua" in metadata["tags"]


def test_auto_publish_false_blocks_public():
    config = AutomationConfig(auto_publish=False)
    assert not can_publicly_publish(
        config,
        {"allowed": True, "risk_level": "low"},
        transformation_applied=True,
        duration_seconds=30,
    )


def test_duration_guard_blocks_public():
    config = AutomationConfig(auto_publish=True, short_max_duration_seconds=58)
    assert not can_publicly_publish(
        config,
        {"allowed": True, "risk_level": "low"},
        transformation_applied=True,
        duration_seconds=59,
    )


def test_low_risk_original_can_publish_public():
    config = AutomationConfig(auto_publish=True, short_max_duration_seconds=58)
    assert can_publicly_publish(
        config,
        {"allowed": True, "risk_level": "low"},
        transformation_applied=True,
        duration_seconds=25,
    )


class FakeRequest:
    calls = 0

    def execute(self):
        FakeRequest.calls += 1
        if FakeRequest.calls == 1:
            raise RuntimeError("transient")
        return {"id": "uploaded123"}


class FakeVideos:
    def insert(self, **kwargs):
        return FakeRequest()


class FakeYouTube:
    def videos(self):
        return FakeVideos()


def test_uploader_retry_with_mocked_client(monkeypatch, tmp_path: Path):
    FakeRequest.calls = 0
    file_path = tmp_path / "short.mp4"
    file_path.write_bytes(b"fake")

    class FakeMedia:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("googleapiclient.http.MediaFileUpload", FakeMedia)
    result = upload_short(
        str(file_path),
        {"title": "Test Short", "description": "", "tags": [], "category_id": "22"},
        youtube_client=FakeYouTube(),
        config=AutomationConfig(),
    )
    assert result["youtube_video_id"] == "uploaded123"
    assert FakeRequest.calls == 2


def test_dry_run_never_uploads(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "automation.yaml"
    config_path.write_text("allowed_channel_ids: ['allowed-channel']\ntopic_keywords: ['python']\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")
    monkeypatch.setenv("AUTOMATION_DB_PATH", str(tmp_path / "automation.sqlite"))
    monkeypatch.setattr(
        "shorts_generator.automation.daily_runner.discover_candidates",
        lambda region, max_results, config: [sample_video()],
    )

    def fail_upload(*args, **kwargs):
        raise AssertionError("dry run should not upload")

    monkeypatch.setattr("shorts_generator.automation.daily_runner.upload_short", fail_upload)
    summary = run_once(config_path=str(config_path), dry_run=True, max_uploads=1)
    assert summary["dry_run"] is True
    assert summary["uploads_completed"] == 0


def test_deploy_env_config(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "automation.yaml"
    config_path.write_text("allowed_channel_ids: []\n", encoding="utf-8")
    monkeypatch.setenv("CHANNEL_NAME", "Kashii4you")
    monkeypatch.setenv("UPLOAD_INTERVAL_HOURS", "8")
    monkeypatch.setenv("UPLOAD_TIMES", "08:00, 14:00, 20:00")
    monkeypatch.setenv("WATERMARK_TEXT", "@Kashii4u")
    config = load_automation_config(str(config_path))
    assert config.channel_name == "Kashii4you"
    assert config.upload_interval_hours == 8
    assert config.upload_times == ["08:00", "14:00", "20:00"]
    assert config.watermark_text == "@Kashii4u"


def test_youtube_token_base64_json_written(tmp_path: Path):
    token = {
        "token": "access",
        "refresh_token": "refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client",
        "client_secret": "secret",
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
    }
    encoded = base64.b64encode(json.dumps(token).encode("utf-8")).decode("ascii")
    config = AutomationConfig(youtube_token_base64=encoded)
    token_path = tmp_path / "token.json"
    _write_token_from_base64(config, token_path)
    assert json.loads(token_path.read_text(encoding="utf-8"))["refresh_token"] == "refresh"


def test_env_check_ready_with_oauth_without_api_key():
    config = AutomationConfig(
        youtube_client_id="client",
        youtube_client_secret="secret",
        youtube_token_base64="token",
    )
    result = check_environment(config)
    assert result["ready"] is True
    assert result["discovery_auth"] == "oauth"


def test_original_topic_short_invokes_ffmpeg(monkeypatch, tmp_path: Path):
    calls = []

    def fake_run(cmd, check):
        calls.append(cmd)
        output = Path(cmd[-1])
        output.write_bytes(b"mp4")

    monkeypatch.setattr("shorts_generator.transform.original_video._download_background", lambda *args, **kwargs: None)
    monkeypatch.setattr("shorts_generator.transform.original_video.subprocess.run", fake_run)
    result = generate_original_topic_short(
        {"title": "AI tools for creators"},
        AutomationConfig(channel_name="Kashii4you", watermark_text="@Kashii4u"),
        out_dir=str(tmp_path),
    )
    assert result["transformation_applied"] is True
    assert result["source_type"] == "original_topic_short"
    assert calls


def test_choose_niche_topic_from_config():
    topic = choose_niche_topic(AutomationConfig(content_niches=["ai_tools"]), seed="20260705-1")
    assert topic["niche"] == "ai_tools"
    assert "script" in topic
    assert topic["video_id"].startswith("ai_tools-")


def test_pick_licensed_audio_rotates(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    first = audio_dir / "a.mp3"
    second = audio_dir / "b.mp3"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    config = AutomationConfig(licensed_audio_dir=str(audio_dir))
    picked = _pick_licensed_audio(config, seed="rotate")
    assert picked in {first, second}


def test_dry_run_returns_niche_candidate(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "automation.yaml"
    config_path.write_text("allowed_channel_ids: []\n", encoding="utf-8")
    monkeypatch.setenv("AUTOMATION_DB_PATH", str(tmp_path / "automation.sqlite"))
    monkeypatch.chdir(tmp_path)
    summary = run_once(config_path=str(config_path), dry_run=True, max_uploads=1)
    assert summary["dry_run"] is True
    assert summary["original_niche_candidate"]["mode"] == "would generate fully original niche short"
