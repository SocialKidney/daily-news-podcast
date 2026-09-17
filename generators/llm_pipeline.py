"""LLM pipeline for generating structured newsletters and conversational 10-minute podcast scripts."""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any
import pytz

from config import config
from collectors.news_collector import NewsStory
from utils.audio_utils import sanitize_text_for_tts

logger = logging.getLogger(__name__)


class LLMPipeline:
    """Orchestrates Gemini LLM generation for daily newsletter and podcast script."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or config.gemini_api_key
        self.client = None
        if self.api_key:
            try:
                from google import genai

                self.client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client.")
            except Exception as e:
                logger.warning("Could not initialize Google GenAI client: %s", e)

    def generate_newsletter_content(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str = ""
    ) -> Dict[str, Any]:
        """
        Generate structured newsletter items from curated stories across 4 tiers.
        Each story will feature:
        - Punchy, accurate headline
        - 2 to 3 concise lines of essential context
        - Source attribution and link
        """
        if not date_str:
            tz = pytz.timezone(config.timezone)
            date_str = datetime.now(tz).strftime("%A, %B %d, %Y")

        if self.client:
            try:
                return self._generate_newsletter_with_gemini(
                    tiered_stories, date_str
                )
            except Exception as e:
                logger.warning(
                    "Gemini newsletter generation failed: %s. Using local synthesis.", e
                )

        return self._generate_newsletter_local_fallback(tiered_stories, date_str)

    def generate_podcast_script(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str = ""
    ) -> str:
        """
        Generate a single-host, conversational, natural-sounding podcast episode script.
        Target word count: 1,300 to 1,500 words (~10 minutes spoken pace at 140-150 wpm).
        Structured flow: Host Intro & Date -> Edmonton -> Alberta -> Canada -> Global -> Outro.
        """
        if not date_str:
            tz = pytz.timezone(config.timezone)
            date_str = datetime.now(tz).strftime("%A, %B %d, %Y")

        if self.client:
            try:
                script = self._generate_podcast_with_gemini(tiered_stories, date_str)
                cleaned = sanitize_text_for_tts(script)
                word_count = len(cleaned.split())
                logger.info("Generated podcast script with %d words.", word_count)
                return cleaned
            except Exception as e:
                logger.warning(
                    "Gemini podcast generation failed: %s. Using fallback script generator.",
                    e,
                )

        script = self._generate_podcast_local_fallback(tiered_stories, date_str)
        return sanitize_text_for_tts(script)

    def _format_stories_prompt_context(
        self, tiered_stories: Dict[str, List[NewsStory]]
    ) -> str:
        """Format stories into clear text context for prompt injection."""
        lines = []
        tier_labels = {
            "edmonton": "EDMONTON LOCAL NEWS",
            "alberta": "ALBERTA PROVINCIAL NEWS",
            "canada": "CANADA NATIONAL NEWS",
            "world": "GLOBAL / INTERNATIONAL NEWS",
        }
        for tier, label in tier_labels.items():
            stories = tiered_stories.get(tier, [])
            lines.append(f"\n--- {label} ---")
            for i, s in enumerate(stories, 1):
                lines.append(f"{i}. Title: {s.title}")
                lines.append(f"   Source: {s.source}")
                lines.append(f"   Summary: {s.summary}")
                lines.append(f"   Link: {s.link}")
        return "\n".join(lines)

    def _generate_newsletter_with_gemini(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str
    ) -> Dict[str, Any]:
        """Invoke Gemini to create structured newsletter JSON."""
        context = self._format_stories_prompt_context(tiered_stories)

        prompt = f"""You are an expert editorial journalist and newsletter writer.
Below are the top curated news stories for today ({date_str}) across four geographic tiers: Edmonton Local, Alberta Provincial, Canada National, and Global World.

For each tier, format the stories into a structured newsletter section where each story has:
1. "headline": A punchy, accurate headline.
2. "context": Exactly 2 to 3 concise, highly informative sentences giving essential background, what happened, and why it matters.
3. "source": The news outlet name.
4. "link": The original source link.

Also provide:
- "date": "{date_str}"
- "summary_lead": A warm 2-sentence editorial overview introducing today's briefing.

Input Stories:
{context}

Respond ONLY with valid JSON in this exact structure:
{{
  "date": "{date_str}",
  "summary_lead": "...",
  "edmonton": [
    {{"headline": "...", "context": "...", "source": "...", "link": "..."}}
  ],
  "alberta": [
    {{"headline": "...", "context": "...", "source": "...", "link": "..."}}
  ],
  "canada": [
    {{"headline": "...", "context": "...", "source": "...", "link": "..."}}
  ],
  "world": [
    {{"headline": "...", "context": "...", "source": "...", "link": "..."}}
  ]
}}
"""

        # Call Gemini models using Interactions API with fallback list
        candidate_models = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3-flash-preview"]
        text_response = ""
        last_error = None

        for model_name in candidate_models:
            try:
                interaction = self.client.interactions.create(
                    model=model_name,
                    input=prompt,
                )
                text_response = interaction.output_text or ""
                if text_response:
                    break
            except Exception as e:
                last_error = e
                logger.debug("Interactions call failed with %s: %s", model_name, e)
                try:
                    res = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    text_response = res.text or ""
                    if text_response:
                        break
                except Exception as e2:
                    last_error = e2
                    logger.debug("generate_content failed with %s: %s", model_name, e2)

        if not text_response:
            raise RuntimeError(f"All Gemini candidate models failed: {last_error}")

        # Parse JSON
        clean_json = text_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        data = json.loads(clean_json)
        return data

    def _generate_podcast_with_gemini(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str
    ) -> str:
        """Invoke Gemini to write a 1,300 to 1,500 word conversational podcast script."""
        context = self._format_stories_prompt_context(tiered_stories)
        target_words = config.target_podcast_words  # Default 1400

        prompt = f"""You are an engaging, articulate, professional podcast host delivering today's comprehensive morning briefing for {date_str}.

You are speaking directly to a listener over coffee or during their morning commute in Edmonton, Alberta.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,300 to 1,500 words). This represents approximately 10 minutes of spoken audio at standard conversation pace.

REQUIREMENTS & STRUCTURE:
1. Warm Intro: Welcome the listener, state today's date ({date_str}), and preview the journey ahead from our backyard here in Edmonton, expanding across Alberta, looking at Canada as a whole, and then scanning key developments around the globe.
2. Edmonton Local News: Dive in-depth into the local stories. Give meaningful context, why it matters to Edmontonians, transit riders, families, or local businesses.
3. Alberta Provincial News: Transition smoothly to the provincial picture. Discuss policy, healthcare, energy, economy, or government developments with nuanced analysis.
4. Canada National News: Expand our lens to federal politics, the national economy, interest rates, or cross-country affairs.
5. Global / World News: Connect Canadian and local listeners to major international headlines, geopolitical movements, or groundbreaking technological/environmental events.
6. Outro: Summarize key takeaways, offer an inspiring or thoughtful concluding thought for the day, and deliver a warm sign-off.

AUDIO & SPOKEN STYLE RULES (CRITICAL):
- This script will be read directly by an AI Text-To-Speech engine.
- Write in 100% natural, spoken, conversational English.
- DO NOT include ANY markdown syntax (no asterisks, no hash signs, no bullet points).
- DO NOT include ANY bracketed stage directions or sound effect cues such as [Intro Music Fades], [Host Chuckles], [Pause], or (Music). Every single word in your output will be spoken aloud.
- Use natural spoken transitions: "Now turning to our provincial beat...", "Looking across the country...", "Shifting our view across the border..."
- Provide rich substance and comprehensive storytelling for each news item to meet the target word count naturally.

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""

        candidate_models = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3-flash-preview"]
        text_response = ""
        last_error = None

        for model_name in candidate_models:
            try:
                interaction = self.client.interactions.create(
                    model=model_name,
                    input=prompt,
                )
                text_response = interaction.output_text or ""
                if text_response:
                    break
            except Exception as e:
                last_error = e
                logger.debug("Interactions call failed with %s: %s", model_name, e)
                try:
                    res = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    text_response = res.text or ""
                    if text_response:
                        break
                except Exception as e2:
                    last_error = e2
                    logger.debug("generate_content failed with %s: %s", model_name, e2)

        if not text_response:
            raise RuntimeError(f"All Gemini candidate models failed: {last_error}")

        return text_response

    def _generate_newsletter_local_fallback(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str
    ) -> Dict[str, Any]:
        """Local fallback to format stories into newsletter data structure."""
        newsletter_data: Dict[str, Any] = {
            "date": date_str,
            "summary_lead": (
                f"Welcome to your curated morning digest for {date_str}. "
                "Here are the top stories shaping Edmonton, Alberta, Canada, and the world today."
            ),
            "edmonton": [],
            "alberta": [],
            "canada": [],
            "world": [],
        }

        for tier in ["edmonton", "alberta", "canada", "world"]:
            stories = tiered_stories.get(tier, [])
            for s in stories:
                context_sentences = s.summary.strip()
                if not context_sentences:
                    context_sentences = f"Key development reported by {s.source} regarding {s.title}."
                newsletter_data[tier].append(
                    {
                        "headline": s.title,
                        "context": context_sentences,
                        "source": s.source,
                        "link": s.link,
                    }
                )

        return newsletter_data

    def _generate_podcast_local_fallback(
        self, tiered_stories: Dict[str, List[NewsStory]], date_str: str
    ) -> str:
        """
        Synthesizes a rich, natural-sounding, 1,300+ word conversational podcast script
        without requiring external LLM API calls, ideal for dry-runs and offline testing.
        """
        paragraphs: List[str] = []

        # Intro
        paragraphs.append(
            f"Good morning, and welcome to your Daily Briefing podcast for {date_str}. "
            "I am your host, and wherever you are tuning in from today, whether you are starting your morning "
            "with a fresh cup of coffee, heading out on your commute across the river, or settling into your workspace, "
            "we have an expansive ten-minute briefing lined up for you. "
            "Our focus today follows a deliberate path: starting right here in our municipal backyard with the latest "
            "developments shaping Edmonton, expanding across Alberta to look at provincial policy and economic momentum, "
            "broadening our perspective to national affairs from coast to coast, and finally scanning the critical headlines "
            "making waves on the global stage. There is a lot of ground to cover, so let us jump right in."
        )

        # Edmonton Section
        paragraphs.append(
            "We begin our morning right here in Edmonton. Local governance, transit infrastructure, and community "
            "services are in sharp focus this week as city officials and residents navigate the evolving needs of our growing metropolitan area."
        )

        edmonton_openers = [
            "Our opening Edmonton story centers on",
            "Next in local developments, we turn to",
            "Rounding out our Edmonton metro coverage,",
        ]
        edmonton_stories = tiered_stories.get("edmonton", [])
        for i, story in enumerate(edmonton_stories):
            opener = edmonton_openers[i % len(edmonton_openers)]
            paragraphs.append(
                f"{opener} {story.title}, reported by {story.source}. "
                f"{story.summary} "
                "For Edmontonians, this is a topic that resonates directly with everyday life. Municipal decision-making "
                "often impacts the essential rhythms of the city, from commute times across major corridors like the Whitemud and Yellowhead, "
                "to neighborhood revitalization and local business activity. Community advocates have highlighted how crucial proactive planning "
                "remains, especially as our population continues to expand and demands on public infrastructure evolve. As council debates continue, "
                "we will be watching closely to see how administration balances immediate service delivery with long-term capital priorities."
            )

        # Transition to Alberta
        paragraphs.append(
            "Stepping back to look at the broader provincial landscape, developments across Alberta are setting the tone "
            "for healthcare, energy transition, and interprovincial relations. With the provincial legislature actively weighing key files, "
            "decisions made in the capital are reverberating from Calgary to Fort McMurray."
        )

        alberta_openers = [
            "Looking first at provincial affairs, our focus turns to",
            "Also making headlines across Alberta,",
            "And concluding our provincial scan,",
        ]
        alberta_stories = tiered_stories.get("alberta", [])
        for i, story in enumerate(alberta_stories):
            opener = alberta_openers[i % len(alberta_openers)]
            paragraphs.append(
                f"{opener} {story.title}, as highlighted by {story.source}. "
                f"{story.summary} "
                "Across Alberta, policy adjustments in this sector have sparked widespread interest among industry leaders, healthcare professionals, "
                "and everyday families. Economists point out that Alberta's unique position, characterized by resource vitality and demographic growth, "
                "demands both fiscal discipline and targeted reinvestment in vital public services. Whether you are following provincial budget updates "
                "or regional job creation programs, this ongoing story illustrates the strategic choices Alberta is making to navigate modern economic pressures."
            )

        # Transition to Canada
        paragraphs.append(
            "Now, expanding our lens across the nation, Canada is grappling with significant economic and federal policy discussions. "
            "From parliamentary debates in Ottawa to shifts in monetary policy and federal-provincial agreements, the national climate "
            "reflects a delicate balance between fiscal prudence and domestic investment."
        )

        canada_openers = [
            "On the national front, our top headline is",
            "Moving across the country, we are tracking",
            "Additionally in federal and national news,",
        ]
        canada_stories = tiered_stories.get("canada", [])
        for i, story in enumerate(canada_stories):
            opener = canada_openers[i % len(canada_openers)]
            paragraphs.append(
                f"{opener} {story.title}, covered by {story.source}. "
                f"{story.summary} "
                "From coast to coast, this issue reflects broader challenges and opportunities confronting Canadian society today. Federal policymakers "
                "are under sustained scrutiny to ensure regulatory frameworks remain responsive to international market realities while protecting consumer interests. "
                "Analysts tracking these developments emphasize that national decisions on infrastructure, trade, and social programming will carry "
                "significant downstream implications for provincial economies right across the country."
            )

        # Transition to World
        paragraphs.append(
            "Finally, we turn our attention across international borders to the global arena. In an increasingly interconnected world, "
            "international trade flows, diplomatic summits, and global technological advancements directly influence domestic supply chains and macroeconomic conditions."
        )

        world_openers = [
            "On the international stage, our primary global report covers",
            "In other international developments shaping world markets,",
            "And rounding out our global scan today,",
        ]
        world_stories = tiered_stories.get("world", [])
        for i, story in enumerate(world_stories):
            opener = world_openers[i % len(world_openers)]
            paragraphs.append(
                f"{opener} {story.title}, brought to us by {story.source}. "
                f"{story.summary} "
                "Global observers are monitoring this development with keen interest. The interplay of international alliances, cross-border commerce, "
                "and technological innovation continues to demonstrate that events abroad rapidly shape consumer sentiment and strategic planning at home. "
                "International analysts underscore the necessity of sustained multilateral cooperation as nations navigate shared economic and environmental challenges."
            )

        # Outro
        paragraphs.append(
            f"That brings us to the close of today's Daily Briefing for {date_str}. "
            "From Edmonton's municipal corridors to the broader provincial stage, across Canada's national landscape, and around the globe, "
            "you are now fully equipped with the facts and context you need to tackle the day ahead. "
            "Don't forget to check the accompanying newsletter in your email inbox for full source links and deeper reading on each of the topics we covered. "
            "Thank you for spending ten minutes of your morning with us. Have a productive, inspiring, and safe day ahead, and we will be back "
            "tomorrow morning with your next comprehensive briefing. Take care."
        )

        return "\n\n".join(paragraphs)
