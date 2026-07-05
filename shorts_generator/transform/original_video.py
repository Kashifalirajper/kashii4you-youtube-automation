"""Generate original Shorts from trend topics and stock/owned-friendly visuals."""
from __future__ import annotations

import os
import re
import subprocess
import textwrap
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from ..config import AutomationConfig
from ..discovery.stock_media import find_stock_context


PREMIUM_STYLE = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "gold": "F7C948",
    "text_font_size": 60,
    "watermark_font_size": 32,
    # These values intentionally stay restrained: premium, readable, not neon.
    "card_opacity": 0.38,
    "background_dim": 0.25,
    "scene_duration": 5,
    "video_duration": 25,
}


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:60] or "original-short"


NICHE_TOPICS: Dict[str, List[Dict[str, object]]] = {
    "islamic_facts": [
        {
            "title": "Allah knows what your heart carries",
            "query": "mosque peaceful",
            "script": [
                "Allah knows what your heart carries.",
                "Even when nobody understands your silence.",
                "Keep making dua.",
                "What is written for you will not miss you.",
                "Trust Allah's timing.",
            ],
        },
        {
            "title": "When life feels heavy",
            "query": "sunrise prayer",
            "script": [
                "When life feels heavy, pause.",
                "Say Alhamdulillah for what remains.",
                "Say Astaghfirullah for what hurts.",
                "Say Hasbunallahu wa ni'mal wakeel.",
                "Allah is enough.",
            ],
        },
    ],
    "urdu_hindi_motivation": [
        {
            "title": "Chhoti mehnat ka secret",
            "query": "person studying desk",
            "script": [
                "Agar motivation nahi aa rahi, phir bhi kaam shuru karo.",
                "Har din sirf ek percent behtar banna hai.",
                "Chhoti mehnat ko underestimate mat karo.",
                "Consistency talent se zyada powerful hoti hai.",
                "Aaj ka chhota step kal ka confidence banata hai.",
            ],
        },
        {
            "title": "Himmat mat haaro",
            "query": "mountain sunrise",
            "script": [
                "Himmat Mat Haaro",
                "Agar raasta mushkil hai, manzil qeemti hai.",
                "Slow progress bhi progress hai.",
                "Bas rukna mat.",
                "Allah mehnat dekh raha hai.",
                "Kal ka confidence aaj ki mehnat se banta hai.",
            ],
        },
    ],
    "tech_tips": [
        {
            "title": "One tech habit that saves time",
            "query": "laptop workspace",
            "script": [
                "Tech Tip",
                "Use keyboard shortcuts for the task you repeat most.",
                "Start with copy, paste, search, and window switching.",
                "Ten saved seconds repeated daily becomes real time.",
                "Follow for simple tech wins.",
            ],
        },
        {
            "title": "Clean your digital workspace",
            "query": "minimal computer desk",
            "script": [
                "Quick Tech Reset",
                "Delete files you do not need.",
                "Rename folders so future you understands them.",
                "A clean desktop makes work feel lighter.",
                "Try it for five minutes today.",
            ],
        },
    ],
    "ai_tools": [
        {
            "title": "Use AI like a real assistant",
            "query": "artificial intelligence workspace",
            "script": [
                "Most people use AI the wrong way.",
                "Do not ask for one final answer only.",
                "Ask it to compare options, find risks, and improve your draft.",
                "The better your instruction, the better the output.",
                "Use AI to think clearer, not lazier.",
            ],
        },
        {
            "title": "Prompt formula for beginners",
            "query": "technology abstract",
            "script": [
                "Simple Prompt Formula",
                "Give role, task, context, and format.",
                "Example: act as a teacher, explain this in five bullets.",
                "Clear instructions save time.",
                "Try this in your next AI chat.",
            ],
        },
    ],
    "kids_educational": [
        {
            "title": "Why the sky looks blue",
            "query": "blue sky children learning",
            "script": [
                "Kids Science",
                "The sky looks blue because sunlight scatters in the air.",
                "Blue light scatters more than other colors.",
                "That is why we see a blue sky on clear days.",
                "Science is everywhere.",
            ],
        },
        {
            "title": "Count with tiny habits",
            "query": "colorful classroom",
            "script": [
                "Learning Time",
                "Count five things around you.",
                "One, two, three, four, five.",
                "Counting becomes easy when you practice daily.",
                "Great job, keep learning.",
            ],
        },
    ],
}


def choose_niche_topic(config: AutomationConfig, seed: Optional[str] = None) -> Dict:
    niches = config.content_niches or list(NICHE_TOPICS)
    available = [niche for niche in niches if niche in NICHE_TOPICS]
    if not available:
        available = ["tech_tips"]
    seed_value = seed or datetime.now(timezone.utc).strftime("%Y%m%d%H")
    index = sum(ord(ch) for ch in seed_value)
    niche = available[index % len(available)]
    topics = NICHE_TOPICS[niche]
    topic = dict(topics[(index // max(1, len(available))) % len(topics)])
    topic["niche"] = niche
    topic["video_id"] = f"{niche}-{_slug(str(topic['title']))}-{seed_value[:10]}"
    topic["category_id"] = config.default_category_id
    topic["tags"] = [niche.replace("_", " "), "original", "shorts"]
    return topic


def _script_from_topic(topic: Dict, config: AutomationConfig) -> List[str]:
    script = topic.get("script")
    if isinstance(script, list) and script:
        return [str(line) for line in script]
    return [str(topic.get("title") or "Original Short"), "A quick original reminder.", "Save this for later."]


def _download_background(topic: Dict, config: AutomationConfig, out_dir: Path) -> Optional[Path]:
    query = str(topic.get("query") or topic.get("title") or "technology abstract").split("|")[0][:80]
    cached = out_dir / f"{_slug(query)}.jpg"
    if cached.exists():
        return cached
    try:
        stock = find_stock_context(query, config)
    except Exception:
        stock = {"unsplash_photos": [], "pexels_videos": []}

    photos = stock.get("unsplash_photos") or []
    if photos:
        url = ((photos[0].get("urls") or {}).get("regular") or "").strip()
        if url:
            path = out_dir / f"{_slug(query)}.jpg"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            path.write_bytes(response.content)
            return path
    return None


def _write_text_file(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def _font_arg(config: AutomationConfig, bold: bool = True) -> str:
    candidates = []
    if config.brand_font_file:
        candidates.append(Path(config.brand_font_file))
    candidates.extend(
        [
            Path("C:/Windows/Fonts/Montserrat-ExtraBold.ttf"),
            Path("C:/Windows/Fonts/Poppins-ExtraBold.ttf"),
            Path("C:/Windows/Fonts/Inter-Black.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return f":fontfile='{_escape_filter_path(candidate)}'"
    return ""


def _escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _caption_files(script: List[str], out_dir: Path, slug: str) -> List[Path]:
    paths = []
    for index, line in enumerate(script[:5]):
        wrapped_lines = textwrap.wrap(line, width=22)
        if len(wrapped_lines) > 2:
            wrapped_lines = [wrapped_lines[0], " ".join(wrapped_lines[1:])[:28].rstrip()]
        wrapped = "\n".join(wrapped_lines[:2])
        path = out_dir / f"{slug}_caption_{index}.txt"
        path.write_text(wrapped, encoding="utf-8")
        paths.append(path)
    return paths


def _highlight_for(line: str) -> str:
    candidates = [
        "Astaghfirullah",
        "Alhamdulillah",
        "Allah",
        "Dua",
        "Sabr",
        "Silence",
        "dua",
        "sabr",
        "barakah",
        "Hasbunallahu",
    ]
    lowered = line.lower()
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate
    return ""


def _premium_drawtext_filters(script: List[str], config: AutomationConfig, out_dir: Path, slug: str) -> str:
    """Premium Islamic Shorts preset.

    The preset uses a slow cinematic background zoom, dark readability layer,
    warm golden glow, glassmorphism-style card, large bold typography, subtle
    highlight glow, bottom progress bar, and watermark safe margins.
    """
    w = PREMIUM_STYLE["width"]
    h = PREMIUM_STYLE["height"]
    gold = PREMIUM_STYLE["gold"]
    duration = PREMIUM_STYLE["scene_duration"]
    total_duration = duration * min(5, len(script))
    font_bold = _font_arg(config, bold=True)
    font_regular = _font_arg(config, bold=False)
    caption_paths = _caption_files(script, out_dir, slug)

    filters = [
        # Cinematic slow zoom from 1.00x to around 1.08x with a small side pan.
        f"scale={w + 140}:{h + 250}:force_original_aspect_ratio=increase",
        f"zoompan=z='1+0.08*on/({total_duration}*30)':x='iw/2-(iw/zoom/2)+25*on/({total_duration}*30)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=30",
        "setsar=1",
        # Warm, readable background grade.
        "eq=brightness=0.05:contrast=1.08:saturation=1.06",
        f"drawbox=x=0:y=0:w=iw:h=ih:color=0x{gold}@0.08:t=fill",
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@{PREMIUM_STYLE['background_dim']}:t=fill",
    ]

    for index, caption_path in enumerate(caption_paths[:5]):
        start = index * duration
        end = start + duration

        # Simulated rounded glass card: layered soft shadow, lighter glass fill,
        # subtle border, and compact line spacing for one or two-line quotes.
        filters.extend(
            [
                f"drawbox=x=106:y=ih*0.43+22:w=iw-212:h=306:color=black@0.12:t=fill:enable='between(t,{start},{end})'",
                f"drawbox=x=98:y=ih*0.43+14:w=iw-196:h=306:color=black@0.14:t=fill:enable='between(t,{start},{end})'",
                f"drawbox=x=82:y=ih*0.43:w=iw-164:h=300:color=0x080808@{PREMIUM_STYLE['card_opacity']}:t=fill:enable='between(t,{start},{end})'",
                f"drawbox=x=82:y=ih*0.43:w=iw-164:h=300:color=white@0.12:t=1:enable='between(t,{start},{end})'",
                f"drawbox=x=116:y=ih*0.43+30:w=iw-232:h=2:color=0x{gold}@0.34:t=fill:enable='between(t,{start},{end})'",
                f"drawtext=textfile='{_escape_filter_path(caption_path)}':"
                "x=(w-text_w)/2:y=(h*0.515)-(text_h/2):"
                f"fontcolor=white:fontsize={PREMIUM_STYLE['text_font_size']}{font_bold}:line_spacing=6:"
                "borderw=3:bordercolor=black@0.78:"
                f"shadowcolor=black@0.62:shadowx=0:shadowy=5:"
                f"enable='between(t,{start},{end})'",
            ]
        )

        highlight = _highlight_for(caption_path.read_text(encoding="utf-8"))
        if highlight:
            highlight_safe = _escape_text(highlight)
            pop_start = start + 0.15
            pop_end = end - 0.15
            filters.extend(
                [
                f"drawbox=x=(iw-420)/2:y=ih*0.388:w=420:h=74:color=0x{gold}@0.035:t=fill:enable='between(t,{pop_start},{pop_end})'",
                f"drawbox=x=(iw-330)/2:y=ih*0.398:w=330:h=52:color=0x{gold}@0.055:t=fill:enable='between(t,{pop_start},{pop_end})'",
                f"drawtext=text='{highlight_safe}':x=(w-text_w)/2:y=h*0.405:"
                f"fontcolor=0x{gold}:fontsize=42{font_bold}:"
                "borderw=2:bordercolor=black@0.62:shadowcolor=0xF7C948@0.45:shadowx=0:shadowy=0:"
                f"enable='between(t,{pop_start},{pop_end})'",
                ]
            )

    # Bottom progress bar: background + animated active width.
    filters.extend(
        [
            "drawbox=x=70:y=ih-22:w=iw-140:h=5:color=white@0.14:t=fill",
            f"drawbox=x=70:y=ih-22:w='(iw-140)*t/{total_duration}':h=5:color=0x{gold}@1:t=fill:enable='lte(t,{total_duration})'",
        ]
    )

    watermark = _escape_text(config.watermark_text or "@Kashii4u")
    filters.append(
        f"drawtext=text='{watermark}':x=w-text_w-54:y=h-96:fontcolor=white@0.55:"
        f"fontsize={PREMIUM_STYLE['watermark_font_size']}{font_regular}:"
        "borderw=2:bordercolor=black@0.35"
    )
    return ",".join(filters)


def _drawtext_filters(script: List[str], config: AutomationConfig, out_dir: Path, slug: str) -> str:
    if config.visual_preset == "premium_islamic_short":
        return _premium_drawtext_filters(script, config, out_dir, slug)

    filters = []
    duration = 8
    caption_paths = _caption_files(script, out_dir, slug)
    font_bold = _font_arg(config, bold=True)
    font_regular = _font_arg(config, bold=False)

    hook = _escape_text("Islamic reminder")
    filters.append(
        "drawbox=x=48:y=54:w=iw-96:h=70:color=black@0.36:t=fill"
    )
    filters.append(
        f"drawtext=text='{hook}':x=(w-text_w)/2:y=76:fontcolor=white:fontsize=28{font_bold}:"
        "borderw=2:bordercolor=black@0.35"
    )

    for index, caption_path in enumerate(caption_paths):
        start = index * duration
        end = start + duration
        fade_in_end = start + 0.45
        fade_out_start = end - 0.45
        filters.append(
            "drawbox=x=44:y=ih*0.50:w=iw-88:h=ih*0.25:color=black@0.68:t=fill:"
            f"enable='between(t,{start},{end})'"
        )
        filters.append(
            "drawbox=x=50:y=ih*0.505:w=iw-100:h=4:color=white@0.22:t=fill:"
            f"enable='between(t,{start},{end})'"
        )
        alpha = (
            f"if(lt(t,{fade_in_end}),(t-{start})/0.45,"
            f"if(gt(t,{fade_out_start}),({end}-t)/0.45,1))"
        )
        filters.append(
            f"drawtext=textfile='{_escape_filter_path(caption_path)}':"
            "x=(w-text_w)/2:y=(h*0.625)-(text_h/2):"
            f"fontcolor=white:fontsize=54{font_bold}:line_spacing=14:"
            "borderw=4:bordercolor=black@0.85:"
            f"alpha='{alpha}':"
            f"enable='between(t,{start},{end})'"
        )

    watermark = _escape_text(config.watermark_text or "@Kashii4u")
    filters.append(
        f"drawtext=text='{watermark}':x=w-text_w-34:y=h-74:fontcolor=white@0.82:fontsize=28{font_regular}:"
        "borderw=2:bordercolor=black@0.45"
    )
    return ",".join(filters)


def _generate_safe_background_audio(out_dir: Path, slug: str, duration: int = 40) -> Path:
    """Generate an original, copyright-safe soft ambient background bed."""
    audio_path = out_dir / f"{slug}_original_bed.wav"
    # A gentle original pad/pulse. This is generated locally, so it avoids
    # copyrighted nasheed/adhan/music samples while still giving the Short mood.
    expr = (
        "0.055*sin(2*PI*146.83*t)"
        "+0.045*sin(2*PI*220.00*t)"
        "+0.035*sin(2*PI*293.66*t)"
        "+0.025*sin(2*PI*440.00*t)"
        "+0.030*sin(2*PI*73.42*t)*exp(-mod(t,2.0)*3)"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':sample_rate=44100:duration={duration}",
        "-af", f"aecho=0.7:0.65:700:0.25,lowpass=f=1800,afade=t=in:st=0:d=1.5,afade=t=out:st={duration - 2}:d=2,volume=0.42",
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    return audio_path


def _audio_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _pick_licensed_audio(config: AutomationConfig, seed: str = "") -> Optional[Path]:
    audio_dir = Path(config.licensed_audio_dir)
    if not audio_dir.exists():
        return None
    all_matches: List[Path] = []
    for pattern in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"):
        all_matches.extend(sorted(audio_dir.glob(pattern)))
    if not all_matches:
        return None
    index = sum(ord(ch) for ch in seed) % len(all_matches) if seed else 0
    return all_matches[index]


def _prepare_background_audio(source: Path, out_dir: Path, slug: str, duration: int = 40) -> Path:
    prepared = out_dir / f"{slug}_licensed_bed.m4a"
    total = _audio_duration(source)
    max_start = max(0.0, total - duration - 2)
    start = min(max_start, max(12.0, max_start * 0.35)) if max_start else 0.0
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.2f}",
        "-i", str(source),
        "-vn",
        "-t", str(duration),
        "-af", f"afade=t=in:st=0:d=1.2,afade=t=out:st={duration - 2}:d=2,volume=0.55",
        "-c:a", "aac",
        str(prepared),
    ]
    subprocess.run(cmd, check=True)
    return prepared


def _generate_ai_voiceover(script: List[str], out_dir: Path, slug: str) -> Optional[Path]:
    if os.getenv("VOICEOVER_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    voice_path = out_dir / f"{slug}_voiceover.mp3"
    narration = " ".join(script)
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            client = OpenAI(timeout=float(os.getenv("OPENAI_TTS_TIMEOUT", "30")))
            try:
                response = client.audio.speech.create(
                    model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                    voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
                    input=narration,
                )
            except Exception:
                response = client.audio.speech.create(
                    model="tts-1",
                    voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
                    input=narration,
                )

            if hasattr(response, "write_to_file"):
                response.write_to_file(voice_path)
            else:
                voice_path.write_bytes(response.content)
            return voice_path if voice_path.exists() else None
        except Exception as e:
            print(f"[original/video] OpenAI voiceover unavailable, trying Edge TTS: {e}", flush=True)

    try:
        import edge_tts

        async def _save() -> None:
            communicate = edge_tts.Communicate(
                narration,
                voice=os.getenv("EDGE_TTS_VOICE", "en-US-JennyNeural"),
                rate=os.getenv("EDGE_TTS_RATE", "+2%"),
            )
            await communicate.save(str(voice_path))

        asyncio.run(_save())
        return voice_path if voice_path.exists() else None
    except Exception as e:
        print(f"[original/video] Edge TTS unavailable, using generated bed only: {e}", flush=True)
        return None


def _audio_inputs_and_filter(voice_path: Optional[Path], bed_path: Path) -> tuple[List[str], List[str]]:
    if voice_path and voice_path.exists():
        return (
            ["-i", str(voice_path), "-i", str(bed_path)],
            [
                "-filter_complex",
                "[2:a]volume=0.18[bed];[1:a][bed]amix=inputs=2:duration=longest:dropout_transition=2[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
            ],
        )
    return (["-i", str(bed_path)], [])


def generate_original_topic_short(
    topic: Dict,
    config: AutomationConfig,
    out_dir: str = "output",
) -> Dict:
    """Create a safe original vertical MP4 from a trend topic.

    The video is not a reupload of the source. The trend title is used only as
    idea/context, and the resulting Short contains original text commentary.
    """
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    title = str(topic.get("title") or "Original Short").strip()
    slug = _slug(title)
    output_path = output_dir / f"original_{slug}.mp4"
    script = _script_from_topic(topic, config)
    video_duration = (
        PREMIUM_STYLE["video_duration"]
        if config.visual_preset == "premium_islamic_short"
        else 40
    )
    _write_text_file(output_dir / f"original_{slug}.txt", script)
    licensed_audio = _pick_licensed_audio(config, seed=slug)
    bed_path = (
        _prepare_background_audio(licensed_audio, output_dir, slug, duration=video_duration)
        if licensed_audio
        else _generate_safe_background_audio(output_dir, slug, duration=video_duration)
    )
    voice_path = _generate_ai_voiceover(script, output_dir, slug)
    audio_inputs, audio_filter = _audio_inputs_and_filter(voice_path, bed_path)

    background = _download_background(topic, config, output_dir)
    vf = _drawtext_filters(script, config, output_dir, slug)

    if background and background.exists():
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(background),
            *audio_inputs,
            "-t", str(video_duration),
            "-vf", vf,
            "-r", "30",
            *audio_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-shortest",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=#111827:s=1080x1920:d={video_duration}:r=30",
            *audio_inputs,
            "-vf", vf,
            "-r", "30",
            *audio_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-shortest",
            str(output_path),
        ]
    subprocess.run(cmd, check=True)

    return {
        "file_path": str(output_path),
        "title": title,
        "script": " ".join(script),
        "duration_seconds": video_duration,
        "transformation_applied": os.path.exists(output_path),
        "synthetic_media_used": voice_path is not None,
        "voiceover_applied": voice_path is not None,
        "background_audio": str(licensed_audio) if licensed_audio else "generated",
        "source_type": "original_topic_short",
    }
