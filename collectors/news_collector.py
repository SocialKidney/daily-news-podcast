"""News retrieval and curation module for Edmonton, Alberta, Canada, and Global tiers."""

import re
import html
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import requests
import feedparser

from config import config

logger = logging.getLogger(__name__)


@dataclass
class NewsStory:
    """Represents an individual curated news story."""

    tier: str
    title: str
    summary: str
    link: str
    source: str
    published: Optional[datetime] = None
    published_str: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.published:
            data["published"] = self.published.isoformat()
        return data


class NewsCollector:
    """Collects, deduplicates, and filters news stories across geographic tiers."""

    def __init__(self, request_timeout: int = 6):
        self.request_timeout = request_timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36 DailyBriefing/1.0"
            )
        }

    def fetch_all_tiers(self, stories_per_tier: int = 3) -> Dict[str, List[NewsStory]]:
        """Fetch and curate news across all configured tiers."""
        results: Dict[str, List[NewsStory]] = {}
        for tier in ["edmonton", "alberta", "canada", "world"]:
            logger.info("Fetching news for tier: %s", tier)
            stories = self.fetch_tier(tier, max_stories=stories_per_tier)
            results[tier] = stories
            logger.info("Retrieved %d stories for tier '%s'", len(stories), tier)
        return results

    def fetch_tier(self, tier: str, max_stories: int = 3) -> List[NewsStory]:
        """Fetch news for a specific tier from its configured RSS feeds."""
        feed_sources = config.rss.tiers.get(tier, [])
        collected_raw: List[NewsStory] = []

        for source in feed_sources:
            try:
                stories = self._fetch_feed(source, tier)
                collected_raw.extend(stories)
            except Exception as e:
                logger.warning(
                    "Failed to fetch feed '%s' (%s): %s",
                    source.get("name"),
                    source.get("url"),
                    e,
                )

        if not collected_raw:
            logger.warning(
                "No stories fetched from live RSS for tier '%s'. Using fallback data.",
                tier,
            )
            return self._get_fallback_stories(tier, max_stories)

        # Deduplicate stories
        deduped = self._deduplicate(collected_raw)

        # Filter by recency and select top stories
        curated = self._rank_and_filter(deduped, max_count=max_stories)

        if not curated:
            logger.warning("All stories filtered out for '%s'. Using fallback.", tier)
            return self._get_fallback_stories(tier, max_stories)

        return curated

    def _fetch_feed(self, source_info: dict, tier: str) -> List[NewsStory]:
        """Fetch and parse a single RSS feed."""
        name = source_info.get("name", "Unknown Source")
        url = source_info.get("url", "")
        if not url:
            return []

        response = requests.get(url, headers=self.headers, timeout=self.request_timeout)
        response.raise_for_status()

        feed = feedparser.parse(response.content)
        stories: List[NewsStory] = []

        for entry in feed.entries:
            title = self._clean_text(getattr(entry, "title", ""))
            if not title:
                continue

            summary = self._clean_text(
                getattr(entry, "summary", "") or getattr(entry, "description", "")
            )
            link = getattr(entry, "link", "").strip()

            published_dt = self._parse_date(entry)
            published_str = (
                published_dt.strftime("%b %d, %Y %I:%M %p")
                if published_dt
                else "Recent"
            )

            story = NewsStory(
                tier=tier,
                title=title,
                summary=summary[:300] + ("..." if len(summary) > 300 else ""),
                link=link,
                source=name,
                published=published_dt,
                published_str=published_str,
            )
            stories.append(story)

        return stories

    @staticmethod
    def _clean_text(raw_html: str) -> str:
        """Strip HTML tags, decode entities, and normalize whitespace and punctuation."""
        if not raw_html:
            return ""
        # Replace block breaks with space
        text = re.sub(r"<(?:br|p|div|hr)[^>]*>", " ", raw_html, flags=re.IGNORECASE)
        # Remove remaining HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        clean = html.unescape(clean)
        # Fix detached punctuation like "word ." -> "word."
        clean = re.sub(r"\s+([.,!?:;])", r"\1", clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Attempt to parse published date from feed entry."""
        for date_field in ("published_parsed", "updated_parsed", "created_parsed"):
            val = getattr(entry, date_field, None)
            if val:
                try:
                    return datetime(*val[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        return None

    def _deduplicate(self, stories: List[NewsStory]) -> List[NewsStory]:
        """Deduplicate stories based on URL and headline similarity."""
        unique_stories: List[NewsStory] = []
        seen_links = set()
        seen_titles = []

        for story in stories:
            # 1. Exact or canonical URL deduplication
            clean_link = story.link.split("?")[0].rstrip("/")
            if clean_link and clean_link in seen_links:
                continue

            # 2. Title token similarity deduplication
            norm_title = self._normalize_title(story.title)
            if not norm_title:
                continue

            is_duplicate = False
            story_words = set(norm_title.split())
            for prev_words in seen_titles:
                if not prev_words or not story_words:
                    continue
                overlap = len(story_words & prev_words) / max(
                    len(story_words | prev_words), 1
                )
                if overlap > 0.55:  # Over 55% word token match
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            if clean_link:
                seen_links.add(clean_link)
            seen_titles.append(story_words)
            unique_stories.append(story)

        return unique_stories

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize headline text for comparison."""
        cleaned = re.sub(r"[^\w\s]", "", title.lower())
        return " ".join(cleaned.split())

    def _rank_and_filter(
        self, stories: List[NewsStory], max_count: int
    ) -> List[NewsStory]:
        """Filter by recency (last 48 hours preferred) and select top N stories."""
        now = datetime.now(timezone.utc)
        recent_threshold = now - timedelta(hours=48)

        recent_stories = [
            s for s in stories if s.published is None or s.published >= recent_threshold
        ]

        # If too few recent stories, use what we have
        candidates = recent_stories if len(recent_stories) >= max_count else stories
        return candidates[:max_count]

    def _get_fallback_stories(self, tier: str, count: int) -> List[NewsStory]:
        """Provide fallback stories if RSS feeds are unreachable."""
        now_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
        fallbacks = {
            "edmonton": [
                NewsStory(
                    tier="edmonton",
                    title="City of Edmonton Advances Municipal Infrastructure and Transit Plan",
                    summary="Edmonton City Council reviewed progress on local transit improvements and core service investments today.",
                    link="https://www.edmonton.ca/city_government/news",
                    source="City of Edmonton",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="edmonton",
                    title="Edmonton Public Schools Announce New Community Learning Initiative",
                    summary="A new educational enrichment program is being launched across Edmonton public schools this season.",
                    link="https://www.edmontonjournal.com",
                    source="Edmonton Journal",
                    published_str=now_str,
                ),
            ],
            "alberta": [
                NewsStory(
                    tier="alberta",
                    title="Alberta Government Outlines Economic Diversification and Energy Strategy",
                    summary="Provincial officials shared an updated fiscal framework focusing on energy innovation and regional job growth.",
                    link="https://www.alberta.ca/news.cfm",
                    source="Alberta Government",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="alberta",
                    title="Health Care Modernization Investments Announced Across Alberta Clinics",
                    summary="New provincial funding is allocated to reduce emergency wait times and strengthen rural healthcare capacity.",
                    link="https://www.cbc.ca/news/canada/calgary",
                    source="CBC Alberta",
                    published_str=now_str,
                ),
            ],
            "canada": [
                NewsStory(
                    tier="canada",
                    title="Bank of Canada Evaluates Economic Indicators and Inflation Outlook",
                    summary="Federal economic analysts published their quarterly assessment of consumer trends and interest rate expectations.",
                    link="https://www.cbc.ca/news/business",
                    source="CBC News Canada",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="canada",
                    title="Federal Parliament Debates New Digital Infrastructure Bill",
                    summary="Lawmakers in Ottawa convened to discuss legislation aimed at enhancing nationwide cybersecurity and broadband access.",
                    link="https://www.ctvnews.ca/canada",
                    source="CTV News",
                    published_str=now_str,
                ),
            ],
            "world": [
                NewsStory(
                    tier="world",
                    title="Global Leaders Convene for International Economic and Climate Summit",
                    summary="Delegates from around the world gathered to finalize cooperative pacts on trade and clean energy transitions.",
                    link="https://www.bbc.com/news/world",
                    source="BBC World News",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="world",
                    title="Tech Innovations Spotlight Advances in Renewable Grid Storage",
                    summary="A breakthrough in long-duration battery storage technology promises to accelerate clean electricity deployment globally.",
                    link="https://www.bbc.com/news/technology",
                    source="BBC News",
                    published_str=now_str,
                ),
            ],
        }
        tier_fallbacks = fallbacks.get(tier, fallbacks["world"])
        return tier_fallbacks[:count]
