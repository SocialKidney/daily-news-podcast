# PodCow Daily Podcast Network & News Briefing Service

An automated, production-ready daily intelligence and multi-podcast network running every day at **7:00 AM Mountain Time** (`America/Edmonton`). Powered by **Google Gemini** for script generation and high-definition speech synthesis, and distributed directly to **Pocket Casts** and podcast apps via GitHub Pages.

---

## The Three Daily Shows

| Show Title | Feed URL (Pocket Casts) | Host / Voice | Content Scope |
| :--- | :--- | :--- | :--- |
| **PodCow Daily News Edmonton** | [`podcast.xml`](https://socialkidney.github.io/daily-news-podcast/podcast.xml) | `Kore` (News Host) | Edmonton Local, Alberta Provincial, Canada National, and Global News |
| **Podcow Oilers and NHL Daily** | [`oilers.xml`](https://socialkidney.github.io/daily-news-podcast/oilers.xml) | `Puck` (Sports Analyst) | Edmonton Oilers in-depth, Pacific Division & Canadian rivals, league-wide NHL |
| **Podcow Global AI Daily** | [`ai.xml`](https://socialkidney.github.io/daily-news-podcast/ai.xml) | `Aoede` (Tech Specialist) | Frontier models, clinical/healthcare AI, semiconductors & compute, global policy |

Web Dashboard: [https://socialkidney.github.io/daily-news-podcast/](https://socialkidney.github.io/daily-news-podcast/)

---

## How to Subscribe in Pocket Casts (Android & Windows)

1. Open **Pocket Casts** on your Android phone, tablet, or Windows browser.
2. Tap the **Search / Discover** tab (the magnifying glass icon).
3. Paste any of the feed links below directly into the search bar:
   - **Daily News Edmonton**: `https://socialkidney.github.io/daily-news-podcast/podcast.xml`
   - **Oilers & NHL Daily**: `https://socialkidney.github.io/daily-news-podcast/oilers.xml`
   - **Global AI Daily**: `https://socialkidney.github.io/daily-news-podcast/ai.xml`
4. Tap **Subscribe**. New episodes will download automatically every morning at 7:00 AM Mountain Time!

---

## Project Structure

```
daily-news-podcast/
├── .env.example              # Environment variables template
├── README.md                 # Complete documentation and user guide
├── requirements.txt          # Python dependencies
├── config.py                 # Centralized configuration & show definitions
├── main.py                   # CLI orchestrator (--show all/edmonton/oilers/ai, --run-now, --dry-run)
├── collectors/
│   ├── __init__.py
│   └── news_collector.py     # Multi-show RSS collector, deduplicator & ranker
├── generators/
│   ├── __init__.py
│   ├── llm_pipeline.py       # Gemini prompt pipelines tailored for each show persona
│   ├── podcast_feed.py       # Apple Podcasts / Pocket Casts XML RSS generator
│   └── tts_synthesizer.py    # Speech generation with chunking, stitching & voice switching
├── deliverers/
│   ├── __init__.py
│   └── mailer.py             # Jinja2 HTML email renderer & SMTP sender
├── public/                   # GitHub Pages hosted feeds & assets
│   ├── index.html            # Web dashboard with 1-click Pocket Casts buttons
│   ├── podcast.xml           # Edmonton news feed
│   ├── oilers.xml            # Oilers & NHL feed
│   ├── ai.xml                # Global AI feed
│   └── assets/               # 1400x1400 high-res cover art JPEG images
├── templates/
│   └── newsletter.html       # Responsive HTML email template
├── utils/
│   ├── __init__.py
│   ├── audio_utils.py        # Micro-fading, ffmpeg auto-detection & MP3 compression
│   └── cover_art.py          # Programmatic 1400x1400 artwork generator
├── tests/
│   ├── test_collector.py     # News fetching & deduplication unit tests
│   ├── test_audio.py         # Audio processing & chunking unit tests
│   ├── test_pipeline.py      # LLM pipeline & template unit tests
│   └── test_shows.py         # Multi-show feeds & artwork unit tests
└── .github/workflows/
    └── daily_briefing.yml    # Automated GitHub Actions workflow (7:00 AM Mountain Time)
```

---

## CLI Usage

### Run All Shows Immediately (Production Run)
```bash
python main.py --run-now
```

### Run an Individual Show
```bash
python main.py --run-now --show oilers
python main.py --run-now --show ai
python main.py --run-now --show edmonton
```

### Preview Dry-Run (Tests News & Scripts without Voice Synthesis)
```bash
python main.py --dry-run --show all
```

### Regenerate 1400x1400 Cover Art Images
```bash
python main.py --generate-covers
```

### Start Local Scheduler (Runs Daily at 7:00 AM MT)
```bash
python main.py --schedule
```

---

## GitHub Actions Cloud Automation

The included GitHub Actions workflow (`.github/workflows/daily_briefing.yml`) runs completely hands-free on GitHub's cloud servers:
1. Triggers every morning at 7:00 AM Mountain Time (13:00 UTC during MDT / 14:00 UTC during MST).
2. Runs all three shows sequentially.
3. Uploads generated MP3s to GitHub Releases under `vYYYYMMDD`.
4. Commits updated XML RSS feeds and 30-day episode history to `main`.
5. Deploys updated feeds and cover art to GitHub Pages.
