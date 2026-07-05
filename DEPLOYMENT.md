# Production Deployment

This project is configured for fully original Shorts first: it creates a niche
video, adds your licensed naat/background audio from `assets/audio`, renders the
`premium_islamic_short` style, and uploads to YouTube publicly when the safety
gate passes.

Do not commit real secrets. Keep them in `.env`, GitHub Actions secrets, or your
hosting provider's environment variables.

## Required Secrets

- `CHANNEL_NAME`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_TOKEN_BASE64`

## Recommended Secrets

- `PEXELS_API_KEY`
- `UNSPLASH_ACCESS_KEY`
- `WATERMARK_TEXT`
- `CONTENT_NICHES=islamic_facts`
- `UPLOAD_INTERVAL_HOURS=8`
- `UPLOAD_TIMES=08:00,14:00,20:00`

Optional:

- `OPENAI_API_KEY` only if `VOICEOVER_ENABLED=true`
- `YOUTUBE_API_KEY` only if you later re-enable trend discovery
- `MUAPI_API_KEY` only for the legacy API clipping mode

## Safe Production Defaults

```text
AUTO_PUBLISH=true
DEFAULT_UPLOAD_PRIVACY=public
DAILY_MAX_UPLOADS=1
VISUAL_PRESET=premium_islamic_short
VOICEOVER_ENABLED=false
LICENSED_AUDIO_DIR=assets/audio
OUTPUT_DIR=/data/output
LOGS_DIR=/data/logs
AUTOMATION_DB_PATH=/data/automation.sqlite
```

With these defaults, the automation can run every 8 hours and upload public
videos after the original-content safety gate passes. For testing, set
`AUTO_PUBLISH=false` and `DEFAULT_UPLOAD_PRIVACY=private`.

## Local Test

Dry run:

```powershell
.\scripts\deploy_test.ps1 -DryRun
```

Generate and upload one public Short when the safety gate passes:

```powershell
.\scripts\deploy_test.ps1
```

Check status:

```powershell
.\.venv\Scripts\python.exe automation.py status --last 5
```

## Docker VPS Deploy

Create `.env` from `.env.example`, then run:

```bash
docker compose up --build -d
docker compose logs -f shorts-automation
```

Persistent runtime files are stored in:

```text
./data/output
./data/logs
./data/automation.sqlite
```

The scheduler runs immediately, then repeats every `UPLOAD_INTERVAL_HOURS`
hours.

## GitHub Actions Deploy

1. Push the repo to GitHub.
2. Add the required secrets in **Settings > Secrets and variables > Actions**.
3. Open **Actions > Daily Safe Shorts**.
4. Click **Run workflow**.

The workflow uses local/original mode, not MuAPI. It uploads logs and generated
MP4 files as build artifacts so you can inspect failed runs.

## Expected Output

Each production pass prints JSON and writes `latest_run.json`:

```json
{
  "shorts_generated": 1,
  "uploads_completed": 1,
  "errors": [],
  "original_niche_upload": {
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "privacy_status": "public"
  },
  "niche": "islamic_facts"
}
```

After a run, check YouTube Studio > Content > Private.

## Security Note

If any API key, OAuth client secret, or YouTube token was pasted into chat,
rotate it before production deployment. Treat those credentials as exposed.
