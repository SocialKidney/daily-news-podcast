"""Podcast RSS Feed Generator adhering to the iTunes / Apple Podcasts / Pocket Casts specification."""

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import email.utils

from config import config


class PodcastFeedManager:
    """Creates and updates the iTunes/RSS 2.0 podcast XML feed."""

    def __init__(
        self,
        feed_path: Path = Path("public/podcast.xml"),
        base_url: str = "https://socialkidney.github.io/daily-news-podcast",
        title: str = "PodCOW 2 - Daily News Edmonton",
        author: str = "Dr. Nikhil Shah",
        description: str = (
            "Your automated 10-minute morning intelligence briefing covering Edmonton Local, "
            "Alberta Provincial, Canada National, and Global News."
        ),
    ):
        self.feed_path = feed_path
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.title = title
        self.author = author
        self.description = description
        self.image_url = f"{self.base_url}/assets/cover.jpg"

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
        """
        Add a new episode to the podcast feed XML and save it.
        If download_url is not provided, defaults to GitHub Releases permanent URL.
        """
        if not download_url:
            download_url = (
                f"https://github.com/SocialKidney/daily-news-podcast/releases/download/"
                f"v{datestamp}/{mp3_filename}"
            )

        # Parse existing feed or create a new one
        if self.feed_path.exists():
            try:
                tree = ET.parse(self.feed_path)
                root = tree.getroot()
                channel = root.find("channel")
            except Exception:
                root, channel = self._create_empty_feed()
        else:
            root, channel = self._create_empty_feed()

        # Format duration MM:SS
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins:02d}:{secs:02d}"

        # RFC 2822 date format for pubDate
        now_utc = datetime.now(timezone.utc)
        pub_date = email.utils.format_datetime(now_utc)

        guid_text = f"podcow-edmonton-{datestamp}"
        episode_title = f"PodCOW 2: Daily Briefing - {date_str}"

        # Check if episode with this guid already exists and remove old one
        for existing_item in channel.findall("item"):
            guid_elem = existing_item.find("guid")
            if guid_elem is not None and guid_elem.text == guid_text:
                channel.remove(existing_item)

        # Create new <item> element
        item = ET.Element("item")

        title_el = ET.SubElement(item, "title")
        title_el.text = episode_title

        desc_el = ET.SubElement(item, "description")
        desc_el.text = summary_html

        guid_el = ET.SubElement(item, "guid", attrib={"isPermaLink": "false"})
        guid_el.text = guid_text

        pubdate_el = ET.SubElement(item, "pubDate")
        pubdate_el.text = pub_date

        enclosure_el = ET.SubElement(
            item,
            "enclosure",
            attrib={
                "url": download_url,
                "length": str(mp3_filesize),
                "type": "audio/mpeg",
            },
        )

        duration_el = ET.SubElement(item, "itunes:duration")
        duration_el.text = duration_str

        explicit_el = ET.SubElement(item, "itunes:explicit")
        explicit_el.text = "no"

        author_el = ET.SubElement(item, "itunes:author")
        author_el.text = self.author

        # Insert new episode at the top of channel (after channel metadata)
        # Find index of first item or append
        items = channel.findall("item")
        if items:
            first_item_index = list(channel).index(items[0])
            channel.insert(first_item_index, item)
        else:
            channel.append(item)

        # Write formatted XML
        self._write_pretty_xml(root, self.feed_path)
        return self.feed_path

    def _create_empty_feed(self):
        """Create root and channel with iTunes podcast headers."""
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")

        root = ET.Element(
            "rss",
            attrib={
                "version": "2.0",
                "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
                "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
            },
        )
        channel = ET.SubElement(root, "channel")

        title_el = ET.SubElement(channel, "title")
        title_el.text = self.title

        link_el = ET.SubElement(channel, "link")
        link_el.text = self.base_url

        lang_el = ET.SubElement(channel, "language")
        lang_el.text = "en-ca"

        author_el = ET.SubElement(channel, "itunes:author")
        author_el.text = self.author

        desc_el = ET.SubElement(channel, "description")
        desc_el.text = self.description

        summary_el = ET.SubElement(channel, "itunes:summary")
        summary_el.text = self.description

        image_el = ET.SubElement(channel, "itunes:image", attrib={"href": self.image_url})

        cat_el = ET.SubElement(channel, "itunes:category", attrib={"text": "News"})
        ET.SubElement(cat_el, "itunes:category", attrib={"text": "Daily News"})

        explicit_el = ET.SubElement(channel, "itunes:explicit")
        explicit_el.text = "no"

        return root, channel

    def _write_pretty_xml(self, root: ET.Element, target_file: Path):
        """Write clean, indented XML string."""
        raw_xml = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(raw_xml)
        pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")

        with open(target_file, "wb") as f:
            f.write(pretty)
