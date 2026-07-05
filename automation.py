"""CLI for daily safe Shorts automation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from shorts_generator.automation.daily_runner import run_once
from shorts_generator.automation.env_check import check_environment
from shorts_generator.automation.scheduler import run_forever
from shorts_generator.config import load_automation_config
from shorts_generator.discovery.youtube_trends import get_trending_videos
from shorts_generator.storage.db import AutomationDB
from shorts_generator.transform.originalize import generate_title_description_tags
from shorts_generator.upload.auth import main as auth_main
from shorts_generator.upload.youtube_uploader import upload_short


def cmd_trends(args: argparse.Namespace) -> int:
    config = load_automation_config(args.config)
    videos = get_trending_videos(region_code=args.region, max_results=args.max_results, config=config)
    print(json.dumps(videos, indent=2))
    return 0


def cmd_run_once(args: argparse.Namespace) -> int:
    summary = run_once(
        region=args.region,
        mode=args.mode,
        max_uploads=args.max_uploads,
        dry_run=args.dry_run,
        force=args.force,
        config_path=args.config,
    )
    print(json.dumps(summary, indent=2))
    return 0 if not summary.get("errors") else 1


def cmd_deploy_run(args: argparse.Namespace) -> int:
    summary = run_once(
        region=args.region,
        mode=args.mode,
        max_uploads=args.max_uploads,
        dry_run=False,
        force=args.force,
        config_path=args.config,
    )
    print(json.dumps(summary, indent=2))
    # A missing trend API key is a configuration problem; ordinary candidate
    # rejection is not. Surface real runner errors to deployment logs.
    return 0 if not summary.get("errors") else 1


def cmd_upload(args: argparse.Namespace) -> int:
    config = load_automation_config(args.config)
    metadata = generate_title_description_tags({"title": args.title}, {"url": ""}, config)
    metadata["title"] = args.title
    result = upload_short(args.file_path, metadata, privacy_status=args.privacy, config=config)
    print(json.dumps(result, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    config = load_automation_config(args.config)
    db = AutomationDB(config.database_path)
    print(json.dumps(db.recent_logs(limit=args.last), indent=2))
    return 0


def cmd_env_check(args: argparse.Namespace) -> int:
    config = load_automation_config(args.config)
    result = check_environment(config)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 1


def cmd_status(args: argparse.Namespace) -> int:
    config = load_automation_config(args.config)
    db = AutomationDB(config.database_path)
    latest_path = Path("logs/latest_run.json")
    latest = None
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    result = {
        "latest_run": latest,
        "recent_uploads": db.recent_uploads(limit=args.last),
        "recent_logs": db.recent_logs(limit=args.last),
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    run_forever(region=args.region, mode=args.mode)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily Safe Shorts Automation")
    parser.add_argument("--config", default="config/automation.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    trends = sub.add_parser("trends", help="Fetch trending YouTube videos")
    trends.add_argument("--region", default="US")
    trends.add_argument("--max-results", type=int, default=20)
    trends.set_defaults(func=cmd_trends)

    run = sub.add_parser("run-once", help="Run one daily automation pass")
    run.add_argument("--region", default="US")
    run.add_argument("--mode", choices=["api", "local"], default="local")
    run.add_argument("--max-uploads", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--force", action="store_true")
    run.set_defaults(func=cmd_run_once)

    deploy = sub.add_parser("deploy-run", help="Run the production scheduled automation pass")
    deploy.add_argument("--region", default="US")
    deploy.add_argument("--mode", choices=["api", "local"], default="local")
    deploy.add_argument("--max-uploads", type=int, default=None)
    deploy.add_argument("--force", action="store_true")
    deploy.set_defaults(func=cmd_deploy_run)

    upload = sub.add_parser("upload", help="Upload an existing short")
    upload.add_argument("file_path")
    upload.add_argument("--title", required=True)
    upload.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    upload.set_defaults(func=cmd_upload)

    auth = sub.add_parser("auth-youtube", help="Run YouTube OAuth")
    auth.set_defaults(func=lambda args: auth_main())

    report = sub.add_parser("report", help="Show recent automation logs")
    report.add_argument("--last", type=int, default=50)
    report.set_defaults(func=cmd_report)

    status = sub.add_parser("status", help="Show latest run, recent uploads, and logs")
    status.add_argument("--last", type=int, default=5)
    status.set_defaults(func=cmd_status)

    env_check = sub.add_parser("env-check", help="Validate deployment secrets without uploading")
    env_check.set_defaults(func=cmd_env_check)

    serve = sub.add_parser("serve", help="Run forever and upload on the configured interval")
    serve.add_argument("--region", default="US")
    serve.add_argument("--mode", choices=["api", "local"], default="local")
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
