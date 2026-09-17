"""Unit tests for content generation pipeline and mail rendering."""

import pytest
from collectors.news_collector import NewsCollector
from generators.llm_pipeline import LLMPipeline
from deliverers.mailer import Mailer


def test_fallback_podcast_script_length_and_flow():
    collector = NewsCollector()
    stories = {
        tier: collector._get_fallback_stories(tier, count=2)
        for tier in ["edmonton", "alberta", "canada", "world"]
    }

    pipeline = LLMPipeline(api_key="")
    script = pipeline.generate_podcast_script(stories, date_str="Thursday, September 17, 2026")

    words = script.split()
    # Ensure it reaches rich podcast length (close to or above 700-1000 words in fallback, target is 1300-1500)
    assert len(words) >= 600
    assert "Edmonton" in script
    assert "Alberta" in script
    assert "Canada" in script
    assert "September 17, 2026" in script


def test_mailer_render_html_and_text():
    mailer = Mailer()
    newsletter_data = {
        "date": "Thursday, September 17, 2026",
        "summary_lead": "Today's top stories covering municipal, provincial, national, and world events.",
        "edmonton": [
            {
                "headline": "City of Edmonton Expands Transit",
                "context": "Council approved light rail extensions across the river. Construction starts next spring.",
                "source": "CBC Edmonton",
                "link": "https://cbc.ca/edmonton",
            }
        ],
        "alberta": [
            {
                "headline": "Provincial Healthcare Budget Update",
                "context": "New funding announced for regional clinics. Wait times projected to fall.",
                "source": "Alberta Govt",
                "link": "https://alberta.ca",
            }
        ],
        "canada": [
            {
                "headline": "Bank of Canada Rate Decision",
                "context": "Central bank holds rate steady citing positive inflation signals.",
                "source": "CBC News",
                "link": "https://cbc.ca/business",
            }
        ],
        "world": [
            {
                "headline": "Global Climate Summit Concludes",
                "context": "Representatives agreed on renewable grid storage milestones.",
                "source": "BBC World",
                "link": "https://bbc.com/world",
            }
        ],
    }

    html = mailer.render_html(newsletter_data, podcast_filename="podcast_20260917.mp3")
    assert "<!DOCTYPE html>" in html
    assert "City of Edmonton Expands Transit" in html
    assert "Provincial Healthcare Budget Update" in html
    assert "Bank of Canada Rate Decision" in html
    assert "Global Climate Summit Concludes" in html
    assert "podcast_20260917.mp3" in html

    text = mailer.render_plain_text(newsletter_data)
    assert "DAILY BRIEFING & PODCAST - Thursday, September 17, 2026" in text
    assert "EDMONTON LOCAL" in text
    assert "ALBERTA PROVINCIAL" in text
