"""Unit tests for news collector, deduplication, and parsing."""

import pytest
from datetime import datetime, timezone
from collectors.news_collector import NewsCollector, NewsStory


def test_clean_text():
    raw = "<p>This is a <b>bold</b> test &amp; story.<br>Read more at <a href='#'>site</a>.</p>"
    cleaned = NewsCollector._clean_text(raw)
    assert cleaned == "This is a bold test & story. Read more at site."


def test_normalize_title():
    t1 = "City of Edmonton: New LRT Line Opens!"
    t2 = "city of edmonton new lrt line opens"
    assert NewsCollector._normalize_title(t1) == NewsCollector._normalize_title(t2)


def test_deduplication():
    collector = NewsCollector()
    stories = [
        NewsStory(
            tier="edmonton",
            title="Edmonton City Council passes budget for 2026",
            summary="Budget passed today.",
            link="https://www.cbc.ca/news/budget-1",
            source="CBC",
        ),
        NewsStory(
            tier="edmonton",
            title="Edmonton City Council passes budget for 2026",  # Exact duplicate title
            summary="Duplicate summary.",
            link="https://www.cbc.ca/news/budget-2",
            source="CBC",
        ),
        NewsStory(
            tier="edmonton",
            title="City Council in Edmonton passes the 2026 budget",  # Similar wording
            summary="Another report.",
            link="https://globalnews.ca/budget",
            source="Global News",
        ),
        NewsStory(
            tier="edmonton",
            title="Unrelated Edmonton festival kicks off downtown",  # Unique
            summary="Festival news.",
            link="https://edmontonjournal.com/festival",
            source="Edmonton Journal",
        ),
    ]

    deduped = collector._deduplicate(stories)
    assert len(deduped) == 2
    assert deduped[0].title == "Edmonton City Council passes budget for 2026"
    assert deduped[1].title == "Unrelated Edmonton festival kicks off downtown"


def test_fallback_stories():
    collector = NewsCollector()
    for tier in ["edmonton", "alberta", "canada", "world"]:
        stories = collector._get_fallback_stories(tier, count=3)
        assert len(stories) == 2  # default fallback count per tier is 2
        assert stories[0].tier == tier
        assert len(stories[0].title) > 0
        assert len(stories[0].summary) > 0
        assert stories[0].link.startswith("http")
