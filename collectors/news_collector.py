"""News retrieval and curation module for multi-podcast network."""

import re
import html
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import requests
import feedparser

from config import config, ShowConfig

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
    """Collects, deduplicates, and filters news stories across custom tiers for any show."""

    def __init__(self, request_timeout: int = 8):
        self.request_timeout = request_timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36 DailyBriefing/1.0"
            )
        }

    def fetch_show_tiers(
        self, show: ShowConfig, stories_per_tier: int = 3
    ) -> Dict[str, List[NewsStory]]:
        """Fetch and curate news across all configured tiers for a specific show."""
        results: Dict[str, List[NewsStory]] = {}
        for tier_name, sources in show.tiers.items():
            logger.info("Fetching news for show '%s', tier '%s'", show.id, tier_name)
            stories = self.fetch_tier(tier_name, feed_sources=sources, max_stories=stories_per_tier)
            results[tier_name] = stories
            logger.info("Retrieved %d stories for tier '%s'", len(stories), tier_name)
        return results

    def fetch_all_tiers(self, stories_per_tier: int = 3) -> Dict[str, List[NewsStory]]:
        """Backwards-compatible helper: fetches tiers for the default edmonton news show."""
        edmonton_show = config.get_show("edmonton")
        if edmonton_show:
            return self.fetch_show_tiers(edmonton_show, stories_per_tier=stories_per_tier)
        return {}

    def fetch_tier(
        self,
        tier: str,
        feed_sources: Optional[List[dict]] = None,
        max_stories: int = 3,
    ) -> List[NewsStory]:
        """Fetch news for a specific tier from its configured RSS feeds."""
        if feed_sources is None:
            # Look up from edmonton show as default
            ed_show = config.get_show("edmonton")
            feed_sources = ed_show.tiers.get(tier, []) if ed_show else []

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
        text = re.sub(r"<(?:br|p|div|hr)[^>]*>", " ", raw_html, flags=re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", "", text)
        clean = html.unescape(clean)
        # Remove WordPress and news aggregator boilerplate
        clean = re.sub(r"The post .*? appeared (?:first on )?.*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\[&#8230;\]|\[\.\.\.\]", "", clean)
        clean = re.sub(r"\s+([.,!?:;])", r"\1", clean)
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
            clean_link = story.link.split("?")[0].rstrip("/")
            if clean_link and clean_link in seen_links:
                continue

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
                if overlap > 0.55:
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

        candidates = recent_stories if len(recent_stories) >= max_count else stories
        filtered: List[NewsStory] = []
        for s in candidates:
            title_lower = s.title.lower()
            # Filter out archival reprints or misleading historical references
            if "babcock" in title_lower and ("oilers" in title_lower or s.tier in ("oilers", "edmonton")):
                continue
            filtered.append(s)
        return filtered[:max_count]

    def _get_fallback_stories(self, tier: str, count: int) -> List[NewsStory]:
        """Provide fallback stories if RSS feeds are unreachable."""
        now_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
        fallbacks = {
            # Edmonton News Show
            "edmonton": [
                NewsStory(
                    tier="edmonton",
                    title="City of Edmonton Advances Core Transit and Infrastructure Priority Plan",
                    summary="Edmonton City Council reviewed progress on LRT network expansions, downtown safety, and municipal service investments.",
                    link="https://www.edmonton.ca/city_government/news",
                    source="City of Edmonton",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="edmonton",
                    title="Edmonton Public Schools Expand Community Learning and Technology Labs",
                    summary="New enrichment programming is launching across Edmonton area high schools and STEM facilities.",
                    link="https://www.edmontonjournal.com",
                    source="Edmonton Journal",
                    published_str=now_str,
                ),
            ],
            "alberta": [
                NewsStory(
                    tier="alberta",
                    title="Alberta Government Outlines Energy Innovation and Technology Capital Grants",
                    summary="Provincial officials shared updated funding allocations targeting clean grid technology and petrochemical investment.",
                    link="https://www.alberta.ca/news.cfm",
                    source="Alberta Government",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="alberta",
                    title="Modernization Funding Announced for Regional Healthcare Facilities Across Alberta",
                    summary="Investments aim to bolster surgical capacity, reduce emergency wait times, and expand clinical training.",
                    link="https://www.cbc.ca/news/canada/calgary",
                    source="CBC Alberta",
                    published_str=now_str,
                ),
            ],
            "canada": [
                NewsStory(
                    tier="canada",
                    title="Bank of Canada Assesses Inflation Outlook and National Economic Trajectory",
                    summary="Economic policymakers released their quarterly monetary policy summary highlighting employment figures and interest rate expectations.",
                    link="https://www.cbc.ca/news/business",
                    source="CBC News Canada",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="canada",
                    title="Parliament Focuses on National Housing Strategy and Digital Trade Policies",
                    summary="Federal ministers in Ottawa reviewed legislative frameworks to speed infrastructure delivery across provinces.",
                    link="https://www.ctvnews.ca/canada",
                    source="CTV News",
                    published_str=now_str,
                ),
            ],
            "world": [
                NewsStory(
                    tier="world",
                    title="Global Leaders Finalize Cooperative Agreements at International Economic Forum",
                    summary="Delegates from major global economies reached consensus on sustainable supply chains and trade stability.",
                    link="https://www.bbc.com/news/world",
                    source="BBC World News",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="world",
                    title="Renewable Energy Storage Milestones Set New Benchmark for Grid Reliability",
                    summary="Next-generation battery technology tests demonstrate extended duration capabilities for utility grids.",
                    link="https://www.bbc.com/news/technology",
                    source="BBC News",
                    published_str=now_str,
                ),
            ],
            # Oilers & NHL Show
            "oilers": [
                NewsStory(
                    tier="oilers",
                    title="Edmonton Oilers Set Line Combinations and Special Teams Focus at Training Camp",
                    summary="Head coach Kris Knoblauch and staff evaluated top-six forward pairings and penalty-kill structures following practice at Rogers Place.",
                    link="https://oilersnation.com",
                    source="OilersNation",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="oilers",
                    title="Connor McDavid and Leon Draisaitl Lead Intensive High-Tempo Scrimmage",
                    summary="The Oilers star duo showcased chemistry with new line additions as preparations ramp up for the upcoming campaign.",
                    link="https://edmontonjournal.com/category/sports/hockey/nhl/edmonton-oilers/",
                    source="Edmonton Journal",
                    published_str=now_str,
                ),
            ],
            "pacific_canadian": [
                NewsStory(
                    tier="pacific_canadian",
                    title="Calgary Flames and Vancouver Canucks Prepare for Pacific Division Rivalry Clashes",
                    summary="Pacific Division rivals refine their blue-line pairings and goaltending rotations ahead of opening week.",
                    link="https://calgaryherald.com/category/sports/hockey/nhl/calgary-flames/",
                    source="Calgary Herald",
                    published_str=now_str,
                ),
            ],
            "nhl_league": [
                NewsStory(
                    tier="nhl_league",
                    title="NHL Previews Key Calder Trophy Contenders and League-Wide Trade Speculation",
                    summary="Analysts break down incoming rookie talent and roster movement as teams finalize 23-man rosters.",
                    link="https://thehockeynews.com",
                    source="The Hockey News",
                    published_str=now_str,
                ),
            ],
            # Global AI Show
            "frontier_models": [
                NewsStory(
                    tier="frontier_models",
                    title="Frontier AI Labs Unveil Next-Generation Multimodal Reasoning and Tool Use Models",
                    summary="New benchmarks demonstrate significant leaps in autonomous reasoning, software synthesis, and complex planning capabilities.",
                    link="https://techcrunch.com/category/artificial-intelligence/",
                    source="TechCrunch AI",
                    published_str=now_str,
                ),
                NewsStory(
                    tier="frontier_models",
                    title="Open-Source AI Ecosystem Surges with High-Efficiency Distilled Foundation Models",
                    summary="New open-weight models deliver competitive reasoning performance on standard consumer and edge hardware.",
                    link="https://www.marktechpost.com",
                    source="MarkTechPost",
                    published_str=now_str,
                ),
            ],
            "clinical_health_ai": [
                NewsStory(
                    tier="clinical_health_ai",
                    title="Clinical AI Diagnostics and Pathology Systems Secure Broad Hospital Deployments",
                    summary="Peer-reviewed clinical studies show major efficiency gains in diagnostic radiology triage and automated ambient physician note transcription.",
                    link="https://medcitynews.com",
                    source="MedCity News",
                    published_str=now_str,
                ),
            ],
            "compute_and_industry": [
                NewsStory(
                    tier="compute_and_industry",
                    title="Hyperscalers and Semiconductor Giants Ramp Next-Gen Silicon and Liquid-Cooled Data Centers",
                    summary="Billions in capital expenditure flow toward custom silicon accelerators and gigawatt-scale infrastructure.",
                    link="https://feeds.arstechnica.com",
                    source="Ars Technica",
                    published_str=now_str,
                ),
            ],
            "policy_and_society": [
                NewsStory(
                    tier="policy_and_society",
                    title="Global Regulatory Frameworks Align on Safety Standards and Transparent Model Auditing",
                    summary="International policy leaders convene to establish verified compliance criteria for frontier AI safety evaluations.",
                    link="https://www.wired.com",
                    source="Wired AI",
                    published_str=now_str,
                ),
            ],
        }
        tier_fallbacks = fallbacks.get(tier, fallbacks.get("world", []))
        return tier_fallbacks[:count]
