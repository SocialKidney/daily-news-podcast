"""Centralized configuration for Daily News Briefing & Podcast Generator."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if available
load_dotenv(BASE_DIR / ".env")


@dataclass
class RSSConfig:
    """RSS Feed endpoints categorized by geographic tier."""

    tiers: Dict[str, List[Dict[str, str]]] = field(
        default_factory=lambda: {
            "edmonton": [
                {
                    "name": "Global News Edmonton",
                    "url": "https://globalnews.ca/edmonton/feed/",
                },
                {
                    "name": "CBC Edmonton",
                    "url": "https://rss.cbc.ca/lineup/canada-edmonton.xml",
                },
                {
                    "name": "Edmonton Journal",
                    "url": "https://edmontonjournal.com/feed/",
                },
            ],
            "alberta": [
                {
                    "name": "Global News Calgary",
                    "url": "https://globalnews.ca/calgary/feed/",
                },
                {
                    "name": "Calgary Herald",
                    "url": "https://calgaryherald.com/feed/",
                },
                {
                    "name": "CBC Alberta",
                    "url": "https://rss.cbc.ca/lineup/canada-calgary.xml",
                },
            ],
            "canada": [
                {
                    "name": "Global News Canada",
                    "url": "https://globalnews.ca/canada/feed/",
                },
                {
                    "name": "CBC Canada Top Stories",
                    "url": "https://rss.cbc.ca/lineup/topstories.xml",
                },
                {
                    "name": "CTV News",
                    "url": "https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009",
                },
            ],
            "world": [
                {
                    "name": "BBC World News",
                    "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
                },
                {
                    "name": "NPR World News",
                    "url": "https://feeds.npr.org/1004/rss.xml",
                },
                {
                    "name": "Al Jazeera English",
                    "url": "https://www.aljazeera.com/xml/rss/all.xml",
                },
            ],
        }
    )


@dataclass
class AppConfig:
    """Main Application Configuration."""

    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    sender_email: str = field(
        default_factory=lambda: os.getenv("SENDER_EMAIL", "").strip()
    )
    sender_app_password: str = field(
        default_factory=lambda: os.getenv("SENDER_APP_PASSWORD", "").strip()
    )
    smtp_host: str = field(
        default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    )
    smtp_port: int = field(
        default_factory=lambda: int(os.getenv("SMTP_PORT", "587"))
    )
    recipient_email: str = field(
        default_factory=lambda: os.getenv("RECIPIENT_EMAIL", "").strip()
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "America/Edmonton").strip()
    )
    schedule_time: str = field(
        default_factory=lambda: os.getenv("SCHEDULE_TIME", "07:00").strip()
    )
    tts_engine: str = field(
        default_factory=lambda: os.getenv("TTS_ENGINE", "gemini").strip().lower()
    )
    voice_name: str = field(
        default_factory=lambda: os.getenv("VOICE_NAME", "Kore").strip()
    )
    target_podcast_words: int = field(
        default_factory=lambda: int(os.getenv("TARGET_PODCAST_WORDS", "1400"))
    )
    output_dir: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("OUTPUT_DIR", "output")
    )
    rss: RSSConfig = field(default_factory=RSSConfig)

    def __post_init__(self):
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def recipient_list(self) -> List[str]:
        """Return recipients as a cleaned list."""
        if not self.recipient_email:
            return []
        return [r.strip() for r in self.recipient_email.split(",") if r.strip()]

    def is_gemini_ready(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.gemini_api_key)

    def is_email_ready(self) -> bool:
        """Check if SMTP credentials and recipients are properly configured."""
        return bool(self.sender_email and self.sender_app_password and self.recipient_list)


# Singleton config instance
config = AppConfig()
