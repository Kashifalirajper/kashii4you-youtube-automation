# Kashii4you YouTube Automation

Production-ready automation for generating original Islamic reminder Shorts for
the Kashii4you channel.

The system creates a new vertical Short, uses owned/licensed background naats
from `assets/audio`, renders a premium Islamic visual preset, and uploads to
YouTube publicly when the safety gate passes.

## What It Does

- Generates fully original niche Shorts, not reused creator footage.
- Uses the `premium_islamic_short` visual style.
- Supports Islamic facts, Urdu/Hindi motivation, tech tips, AI tools, and kids
  educational niches.
- Selects background audio from `assets/audio`.
- Adds the `@Kashii4u` watermark.
- Uploads to YouTube through the official YouTube Data API.
- Runs manually, through Docker, or automatically every 8 hours with GitHub
  Actions.

## Production Defaults

Production is configured for public uploads:

```text
AUTO_PUBLISH=true
DEFAULT_UPLOAD_PRIVACY=public
DAILY_MAX_UPLOADS=1
UPLOAD_INTERVAL_HOURS=8
VISUAL_PRESET=premium_islamic_short
VOICEOVER_ENABLED=false
LICENSED_AUDIO_DIR=assets/audio
```

For testing, set `AUTO_PUBLISH=false` and `DEFAULT_UPLOAD_PRIVACY=private`.

## Required Secrets

Add these to GitHub Actions secrets or to a local `.env` file:

```text
CHANNEL_NAME=Kashii4you
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_TOKEN_BASE64=...
WATERMARK_TEXT=@Kashii4u
```

Recommended:

```text
PEXELS_API_KEY=...
UNSPLASH_ACCESS_KEY=...
CONTENT_NICHES=islamic_facts
UPLOAD_TIMES=08:00,14:00,20:00
UPLOAD_INTERVAL_HOURS=8
```

Optional:

```text
OPENAI_API_KEY=...
VOICEOVER_ENABLED=false
```

OpenAI is only needed if AI voiceover is enabled.

## Local Test

Install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dry run:

```powershell
.\.venv\Scripts\python.exe automation.py run-once --region US --mode local --max-uploads 1 --dry-run
```

Generate and upload one public Short when the safety gate passes:

```powershell
.\.venv\Scripts\python.exe automation.py deploy-run --region US --mode local --max-uploads 1
```

Check status:

```powershell
.\.venv\Scripts\python.exe automation.py status --last 5
```

## GitHub Actions Deploy

This repo includes:

```text
.github/workflows/daily-shorts.yml
```

The workflow:

1. Runs every 8 hours.
2. Installs Python and FFmpeg.
3. Generates one original Short.
4. Uploads it to YouTube as public when the safety gate passes.
5. Saves logs and generated MP4 artifacts.

To test:

1. Push this repo to GitHub.
2. Add the required secrets in **Settings > Secrets and variables > Actions**.
3. Open **Actions > Daily Safe Shorts**.
4. Click **Run workflow**.
5. Check YouTube Studio > Content > Private.

## Docker Deploy

Create a `.env` file from `.env.example`, then run:

```bash
docker compose up --build -d
docker compose logs -f shorts-automation
```

Persistent runtime files are stored in:

```text
data/output
data/logs
data/automation.sqlite
```

## Audio

Put only owned or properly licensed naats/background audio in:

```text
assets/audio
```

The automation rotates through available audio files. If no audio is available,
it generates a simple copyright-safe background bed.

## Security

Never commit `.env`, `token.json`, OAuth client secrets, generated videos, or
SQLite databases. They are ignored by `.gitignore`.

If any keys were pasted into chat or shared publicly, rotate them before
production deployment.

## Repository Name

Recommended GitHub repository slug:

```text
kashii4you-youtube-automation
```

GitHub URLs cannot contain spaces, so use hyphens instead of
`kashii4you youtube automation`.
