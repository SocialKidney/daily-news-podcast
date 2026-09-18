"""Podcast RSS Feed Generator adhering to the iTunes / Apple Podcasts / Pocket Casts specification."""

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import email.utils
from jinja2 import Template

from config import config, ShowConfig

PODCAST_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{{ title | e }}</title>
    <link>{{ base_url | e }}</link>
    <language>en-ca</language>
    <itunes:author>{{ author | e }}</itunes:author>
    <description>{{ description | e }}</description>
    <itunes:summary>{{ description | e }}</itunes:summary>
    <itunes:image href="{{ image_url | e }}"/>
    <itunes:category text="{{ category | e }}">
      {% if subcategory %}<itunes:category text="{{ subcategory | e }}"/>{% endif %}
    </itunes:category>
    <itunes:explicit>no</itunes:explicit>
    {% for ep in episodes %}
    <item>
      <title>{{ ep.title | e }}</title>
      <description><![CDATA[{{ ep.summary_html }}]]></description>
      <guid isPermaLink="false">{{ ep.guid | e }}</guid>
      <pubDate>{{ ep.pub_date }}</pubDate>
      <enclosure url="{{ ep.download_url | e }}" length="{{ ep.filesize }}" type="audio/mpeg"/>
      <itunes:duration>{{ ep.duration }}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:author>{{ author | e }}</itunes:author>
    </item>
    {% endfor %}
  </channel>
</rss>
"""


class PodcastFeedManager:
    """Creates and updates standard iTunes/RSS 2.0 podcast feeds for Pocket Casts & Apple Podcasts."""

    def __init__(
        self,
        feed_path: Path = Path("public/podcast.xml"),
        episodes_json_path: Path = Path("public/episodes.json"),
        base_url: str = "https://socialkidney.github.io/daily-news-podcast",
        title: str = "PodCow Daily News Edmonton",
        author: str = "Dr. Nikhil Shah",
        description: str = (
            "Your automated 10-minute morning intelligence briefing covering Edmonton Local, "
            "Alberta Provincial, Canada National, and Global News."
        ),
        category: str = "News",
        subcategory: str = "Daily News",
        image_filename: str = "cover.jpg",
        show_id: str = "edmonton",
    ):
        self.feed_path = feed_path
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes_json_path = episodes_json_path
        self.base_url = base_url.rstrip("/")
        self.title = title
        self.author = author
        self.description = description
        self.category = category
        self.subcategory = subcategory
        self.image_url = f"{self.base_url}/assets/{image_filename}"
        self.show_id = show_id

    @classmethod
    def for_show(cls, show: ShowConfig) -> "PodcastFeedManager":
        """Factory constructor configured for a specific show."""
        return cls(
            feed_path=Path("public") / show.feed_filename,
            episodes_json_path=Path("public") / show.episodes_filename,
            base_url=config.base_url,
            title=show.title,
            author=config.author,
            description=show.description,
            category=show.category,
            subcategory=show.subcategory,
            image_filename=show.cover_filename,
            show_id=show.id,
        )

    def _load_episodes(self) -> List[Dict[str, Any]]:
        """Load existing episode metadata list."""
        if self.episodes_json_path.exists():
            try:
                with open(self.episodes_json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_episodes(self, episodes: List[Dict[str, Any]]):
        """Save episode metadata list."""
        self.episodes_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.episodes_json_path, "w", encoding="utf-8") as f:
            json.dump(episodes, f, indent=2)

    def add_or_update_episode(
        self,
        date_str: str,
        datestamp: str,
        mp3_filename: str,
        mp3_filesize: int,
        duration_seconds: int,
        summary_html: str,
        download_url: Optional[str] = None,
    ) -> Path:
        """Add a new episode to the feed XML and update episodes.json."""
        if not download_url:
            download_url = (
                f"https://github.com/SocialKidney/daily-news-podcast/releases/download/"
                f"v{datestamp}/{mp3_filename}"
            )

        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins:02d}:{secs:02d}"

        now_utc = datetime.now(timezone.utc)
        pub_date = email.utils.format_datetime(now_utc)
        guid_text = f"podcow-{self.show_id}-{datestamp}"
        episode_title = f"{self.title}: {date_str}"

        episodes = self._load_episodes()

        # Remove duplicate if already exists for this date
        episodes = [ep for ep in episodes if ep.get("guid") != guid_text]

        # Clean any CDATA delimiter issues in summary_html
        safe_summary = (summary_html or "").replace("]]>", "]]&gt;")

        # Prepend new episode (most recent first)
        new_ep = {
            "title": episode_title,
            "summary_html": safe_summary,
            "guid": guid_text,
            "pub_date": pub_date,
            "download_url": download_url,
            "filesize": mp3_filesize,
            "duration": duration_str,
        }
        episodes.insert(0, new_ep)

        # Retain last 30 daily episodes
        episodes = episodes[:30]
        self._save_episodes(episodes)

        # Render XML using Jinja2 template with auto-escaping
        template = Template(PODCAST_XML_TEMPLATE)
        rendered_xml = template.render(
            title=self.title,
            base_url=self.base_url,
            author=self.author,
            description=self.description,
            image_url=self.image_url,
            category=self.category,
            subcategory=self.subcategory,
            episodes=episodes,
        )

        # Validate that XML parses without error
        ET.fromstring(rendered_xml.encode("utf-8"))

        with open(self.feed_path, "w", encoding="utf-8") as f:
            f.write(rendered_xml)

        return self.feed_path
