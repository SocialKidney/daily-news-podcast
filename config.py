"""Centralized configuration for Daily News Briefing & Multi-Podcast Network."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if available
load_dotenv(BASE_DIR / ".env")


@dataclass
class ShowConfig:
    """Configuration for an individual podcast show."""

    id: str
    title: str
    subtitle: str
    description: str
    category: str
    subcategory: str
    voice_name: str
    feed_filename: str
    episodes_filename: str
    cover_filename: str
    target_words: int
    tiers: Dict[str, List[Dict[str, str]]]
    prompt_type: str


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
        default_factory=lambda: os.getenv("TTS_ENGINE", "edge").strip().lower()
    )
    default_voice_name: str = field(
        default_factory=lambda: os.getenv("VOICE_NAME", "en-CA-LiamNeural").strip()
    )
    target_podcast_words: int = field(
        default_factory=lambda: int(os.getenv("TARGET_PODCAST_WORDS", "1400"))
    )
    output_dir: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("OUTPUT_DIR", "output")
    )
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "BASE_URL", "https://socialkidney.github.io/daily-news-podcast"
        ).rstrip("/")
    )
    author: str = field(
        default_factory=lambda: os.getenv("PODCAST_AUTHOR", "Dr. Nikhil Shah").strip()
    )

    shows: Dict[str, ShowConfig] = field(
        default_factory=lambda: {
            "edmonton": ShowConfig(
                id="edmonton",
                title="PodCow Daily News Edmonton",
                subtitle="EDMONTON * ALBERTA * CANADA * WORLD",
                description=(
                    "Your automated 10-minute morning intelligence briefing covering Edmonton Local, "
                    "Alberta Provincial, Canada National, and Global News."
                ),
                category="News",
                subcategory="Daily News",
                voice_name="en-CA-LiamNeural",
                feed_filename="podcast.xml",
                episodes_filename="episodes.json",
                cover_filename="cover.jpg",
                target_words=1400,
                prompt_type="edmonton_news",
                tiers={
                    "edmonton": [
                        {"name": "Global News Edmonton", "url": "https://globalnews.ca/edmonton/feed/"},
                        {"name": "CBC Edmonton", "url": "https://rss.cbc.ca/lineup/canada-edmonton.xml"},
                        {"name": "Edmonton Journal", "url": "https://edmontonjournal.com/feed/"},
                    ],
                    "alberta": [
                        {"name": "Global News Calgary", "url": "https://globalnews.ca/calgary/feed/"},
                        {"name": "Calgary Herald", "url": "https://calgaryherald.com/feed/"},
                        {"name": "CBC Alberta", "url": "https://rss.cbc.ca/lineup/canada-calgary.xml"},
                    ],
                    "canada": [
                        {"name": "Global News Canada", "url": "https://globalnews.ca/canada/feed/"},
                        {"name": "CBC Canada Top Stories", "url": "https://rss.cbc.ca/lineup/topstories.xml"},
                    ],
                    "world": [
                        {"name": "BBC World News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
                        {"name": "NPR World News", "url": "https://feeds.npr.org/1004/rss.xml"},
                        {"name": "Al Jazeera English", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
                    ],
                },
            ),
            "oilers": ShowConfig(
                id="oilers",
                title="Podcow Oilers and NHL Daily",
                subtitle="EDMONTON OILERS & NHL MORNING REPORT",
                description=(
                    "Daily hockey intelligence with an in-depth focus on the Edmonton Oilers, "
                    "Pacific Division and Canadian rivals, and top headlines across the NHL."
                ),
                category="Sports",
                subcategory="Hockey",
                voice_name="en-US-ChristopherNeural",
                feed_filename="oilers.xml",
                episodes_filename="episodes_oilers.json",
                cover_filename="cover_oilers.jpg",
                target_words=1300,
                prompt_type="oilers_hockey",
                tiers={
                    "oilers": [
                        {"name": "OilersNation", "url": "https://oilersnation.com/feed/"},
                        {"name": "Edmonton Journal Oilers", "url": "https://edmontonjournal.com/category/sports/hockey/nhl/edmonton-oilers/feed/"},
                    ],
                    "pacific_canadian": [
                        {"name": "Daily Faceoff", "url": "https://www.dailyfaceoff.com/feed"},
                        {"name": "Calgary Flames (Herald)", "url": "https://calgaryherald.com/category/sports/hockey/nhl/calgary-flames/feed/"},
                        {"name": "Vancouver Canucks (Sun)", "url": "https://vancouversun.com/category/sports/hockey/nhl/vancouver-canucks/feed/"},
                    ],
                    "nhl_league": [
                        {"name": "The Hockey News", "url": "https://thehockeynews.com/.rss/full/"},
                        {"name": "ESPN NHL", "url": "https://www.espn.com/espn/rss/nhl/news"},
                        {"name": "Pro Hockey Rumors", "url": "https://www.prohockeyrumors.com/feed"},
                    ],
                },
            ),
            "ai": ShowConfig(
                id="ai",
                title="Podcow Global AI Daily",
                subtitle="FRONTIER AI, HEALTHCARE & COMPUTE",
                description=(
                    "Daily intelligence covering frontier AI models, breakthroughs in clinical & healthcare AI, "
                    "semiconductors & compute infrastructure, and global AI policy."
                ),
                category="Technology",
                subcategory="Artificial Intelligence",
                voice_name="en-US-AriaNeural",
                feed_filename="ai.xml",
                episodes_filename="episodes_ai.json",
                cover_filename="cover_ai.jpg",
                target_words=1300,
                prompt_type="global_ai",
                tiers={
                    "frontier_models": [
                        {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
                        {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
                        {"name": "MarkTechPost", "url": "https://www.marktechpost.com/feed/"},
                        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
                    ],
                    "clinical_health_ai": [
                        {"name": "MedCity News", "url": "https://medcitynews.com/feed/"},
                        {"name": "Fierce Healthcare", "url": "https://www.fiercehealthcare.com/rss/xml"},
                    ],
                    "compute_and_industry": [
                        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
                        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
                        {"name": "AI News", "url": "https://www.artificialintelligence-news.com/feed/"},
                    ],
                    "policy_and_society": [
                        {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
                    ],
                },
            ),
        }
    )

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

    def get_show(self, show_id: str) -> Optional[ShowConfig]:
        """Retrieve show configuration by ID."""
        return self.shows.get(show_id)


# Singleton config instance
config = AppConfig()
