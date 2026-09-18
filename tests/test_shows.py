"""Tests for the multi-podcast show architecture, feeds, and artwork."""

import pytest
from pathlib import Path
from PIL import Image
import xml.etree.ElementTree as ET

from config import config
from collectors.news_collector import NewsCollector
from generators.podcast_feed import PodcastFeedManager
from utils.cover_art import generate_all_covers


def test_shows_configuration():
    """Verify all 3 requested shows are configured with correct attributes."""
    expected_shows = ["edmonton", "oilers", "ai"]
    for show_id in expected_shows:
        show = config.get_show(show_id)
        assert show is not None
        assert show.title
        assert show.voice_name in ["Kore", "Puck", "Aoede"]
        assert show.feed_filename.endswith(".xml")
        assert show.episodes_filename.endswith(".json")
        assert show.cover_filename.endswith(".jpg")
        assert len(show.tiers) >= 3


def test_feed_generation_for_all_shows(tmp_path):
    """Verify iTunes/Pocket Casts RSS XML generation for all shows without XML errors."""
    for show_id, show in config.shows.items():
        feed_file = tmp_path / f"test_{show.feed_filename}"
        episodes_file = tmp_path / f"test_{show.episodes_filename}"

        mgr = PodcastFeedManager(
            feed_path=feed_file,
            episodes_json_path=episodes_file,
            title=show.title,
            description=show.description,
            category=show.category,
            subcategory=show.subcategory,
            image_filename=show.cover_filename,
            show_id=show.id,
        )

        path = mgr.add_or_update_episode(
            date_str="Thursday, September 17, 2026",
            datestamp="20260917",
            mp3_filename=f"{show_id}_test.mp3",
            mp3_filesize=5000000,
            duration_seconds=540,
            summary_html="<p>Test episode summary with & special characters &amp; entities.</p>",
        )

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert show.title in content
        assert "xmlns:itunes=" in content
        # Ensure it parses as valid XML
        root = ET.fromstring(content.encode("utf-8"))
        channel = root.find("channel")
        assert channel is not None
        item = channel.find("item")
        assert item is not None
        assert item.find("title").text == f"{show.title}: Thursday, September 17, 2026"


def test_cover_art_dimensions_and_quality():
    """Ensure all 3 covers are created at standard 1400x1400 podcast resolution."""
    generate_all_covers()
    for filename in ["cover.jpg", "cover_oilers.jpg", "cover_ai.jpg"]:
        cover_path = Path("public/assets") / filename
        assert cover_path.exists()
        with Image.open(cover_path) as img:
            assert img.size == (1400, 1400)
            assert img.format == "JPEG"
