"""Simple local/server scheduler for repeated production runs."""
from __future__ import annotations

import json
import time
from datetime import datetime
from traceback import format_exc

from ..config import load_automation_config
from .daily_runner import run_once


def run_forever(region: str = "US", mode: str = "local") -> None:
    config = load_automation_config()
    interval = max(1, int(config.upload_interval_hours)) * 3600
    print(f"Starting scheduler: every {config.upload_interval_hours} hours", flush=True)
    while True:
        started = datetime.now().isoformat(timespec="seconds")
        print(f"[{started}] running production pass", flush=True)
        try:
            summary = run_once(region=region, mode=mode, max_uploads=config.daily_max_uploads, dry_run=False)
        except Exception as exc:
            summary = {
                "started_at": started,
                "errors": [f"scheduler pass failed: {exc}"],
                "traceback": format_exc(),
            }
        print(json.dumps(summary, indent=2), flush=True)
        time.sleep(interval)
