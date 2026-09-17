# Daily News Aggregator, Podcast Generator & Email Delivery Service

An automated, production-ready morning news curation and podcast service. Running every day at **7:00 AM Mountain Time** (`America/Edmonton`), it:
1. **Aggregates Top News** across 4 geographic tiers:
   - **Edmonton Local** (CBC Edmonton, Global News Edmonton, Edmonton Journal)
   - **Alberta Provincial** (CBC Alberta/Calgary, Alberta Government News)
   - **Canada National** (CBC News Canada, CTV News, Global News)
   - **Global / World** (BBC World News, CBC World, NPR World)
2. **Generates an Editorial Newsletter** formatted in responsive HTML with punchy headlines, 2–3 sentences of essential context, and source links.
3. **Drafts a Conversational Podcast Script** (~1,300 to 1,500 words, calibrated for ~10 minutes of spoken conversation at 140–150 wpm) with smooth transitions from local to global topics, free of stage directions and markdown.
4. **Synthesizes Audio into MP3** using Google Gemini Speech Generation (`gemini-3.1-flash-tts-preview`) or fallback TTS, chunking text and seamlessly stitching audio segments.
5. **Delivers to Your Inbox** with the responsive HTML newsletter in the body and the MP3 podcast attached.

---

## Project Structure

```
daily-news-podcast/
├── .env.example              # Environment variables template
├── README.md                 # Complete documentation and user guide
├── requirements.txt          # Python dependencies
├── config.py                 # Centralized configuration & feed URLs
├── main.py                   # CLI entry point (--run-now, --dry-run, --schedule)
├── collectors/
│   ├── __init__.py
│   └── news_collector.py     # Multi-tier RSS fetcher, deduplicator & ranker
├── generators/
│   ├── __init__.py
│   ├── llm_pipeline.py       # Gemini prompt pipeline (Newsletter & 10-min Podcast Script)
│   └── tts_synthesizer.py    # Speech generation, chunking & stitching
├── deliverers/
│   ├── __init__.py
│   └── mailer.py             # Jinja2 HTML email renderer & SMTP sender
├── templates/
│   └── newsletter.html       # Responsive HTML email template
├── utils/
│   ├── __init__.py
│   └── audio_utils.py        # Chunking, sanitization, ffmpeg detection & MP3 export
├── tests/
│   ├── test_collector.py     # News fetching & deduplication unit tests
│   ├── test_audio.py         # Audio processing & chunking unit tests
│   └── test_pipeline.py      # LLM pipeline & template unit tests
└── .github/workflows/
    └── daily_briefing.yml    # Automated GitHub Actions workflow (7:00 AM Mountain Time)
```

---

## Prerequisites

- **Python 3.10+** (tested up to Python 3.14)
- **Google Gemini API Key**: Obtain a free or paid API key at [Google AI Studio](https://aistudio.google.com/).
- **Email Account with SMTP**: (e.g. Gmail with a 16-character App Password).

---

## Setup & Installation

### 1. Clone & Install Dependencies

```bash
git clone <your-repo-url>
cd daily-news-podcast

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

> **Note on Windows FFmpeg**: The project bundles `imageio-ffmpeg`, automatically providing a Windows `ffmpeg.exe` binary without requiring manual system PATH configurations.

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and configure your credentials:

```ini
# Google Gemini API Key
GEMINI_API_KEY=AIzaSy...

# Email Delivery Configuration (SMTP)
SENDER_EMAIL=your_email@gmail.com
SENDER_APP_PASSWORD=abcd efgh ijkl mnop
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Target Recipient(s) (comma-separated if multiple)
RECIPIENT_EMAIL=your_email@gmail.com

# Timezone & Schedule
TIMEZONE=America/Edmonton
SCHEDULE_TIME=07:00

# TTS Engine & Preferences
TTS_ENGINE=gemini
VOICE_NAME=Kore
TARGET_PODCAST_WORDS=1400
```

#### How to Generate a Gmail App Password:
1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. Search for or navigate to [App Passwords](https://myaccount.google.com/apppasswords).
4. Name the app `Daily Briefing` and copy the generated 16-character password into `SENDER_APP_PASSWORD` in your `.env`.

---

## Usage

### 1. Test News Retrieval
Verify connectivity to Edmonton, Alberta, Canada, and World RSS feeds:
```bash
python main.py --test-news
```

### 2. Run a Dry Run (Preview Mode)
Runs the full news collection, generates the newsletter, produces the podcast script, and outputs the rendered HTML newsletter and MP3 audio file into the `output/` directory without sending an email:
```bash
python main.py --dry-run
```

Output files generated in `output/`:
- `output/newsletter_YYYYMMDD.html`: The fully rendered responsive HTML newsletter.
- `output/podcast_script_YYYYMMDD.txt`: The conversational podcast script (~1,300 to 1,500 words).
- `output/podcast_YYYYMMDD.mp3`: The synthesized podcast audio file.
- `output/briefing.log`: Timestamped log of the run.

### 3. Immediate Live Execution
Runs the full pipeline end-to-end and delivers the email with the MP3 attachment immediately:
```bash
python main.py --run-now
```

### 4. Continuous Local Scheduler
Starts an APScheduler process that triggers the briefing every morning at **7:00 AM Mountain Time**:
```bash
python main.py --schedule
```

---

## Automated Deployment (GitHub Actions)

A ready-to-run GitHub Actions workflow is provided in `.github/workflows/daily_briefing.yml`.

### Setup in GitHub:
1. Push this repository to GitHub.
2. Go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add the following repository secrets:
   - `GEMINI_API_KEY`: Your Gemini API key.
   - `SENDER_EMAIL`: Your sender Gmail address.
   - `SENDER_APP_PASSWORD`: Your 16-character Google App Password.
   - `RECIPIENT_EMAIL`: The recipient email address.
4. The workflow will automatically execute daily at **7:00 AM Mountain Time** (13:00 UTC during MDT / 14:00 UTC during MST) and can also be triggered manually via the **Run workflow** button in the Actions tab.

---

## Running Automated Tests

Run the test suite with `pytest`:

```bash
pytest -v tests/
```

All tests cover:
- News cleaning, HTML tag removal, and date parsing.
- Title normalization and cross-source deduplication.
- Offline and network fallback mechanisms.
- Text sanitization for TTS (stripping markdown and bracketed cues).
- Script chunking by sentence and paragraph boundaries.
- FFmpeg discovery and audio PCM to WAV conversion.
- Newsletter HTML and plain-text Jinja2 template rendering.

---

## Architecture & Design Highlights

- **Resilient Multi-Source Collection**: If one RSS feed fails or times out, the collector automatically falls back to secondary feeds and local fallbacks, preventing downtime.
- **Natural Spoken Podcast Script**: Prompts are calibrated for single-host spoken audio, pacing, and length (~1,300–1,500 words for ~10 minutes). Non-verbal stage directions are stripped out before speech synthesis.
- **Smart Audio Chunking & Stitching**: Breaks long scripts at sentence boundaries to respect API character limits, then stitches synthesized segments with natural 350ms acoustic pauses into a clean MP3 file.
- **Zero-Setup Audio Pipeline**: Bundles `imageio-ffmpeg` so Windows users do not have to install or configure external FFmpeg binaries.
