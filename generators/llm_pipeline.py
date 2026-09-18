"""LLM pipeline for generating structured newsletters and conversational podcast scripts across shows."""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import pytz

from config import config, ShowConfig
from collectors.news_collector import NewsStory
from utils.audio_utils import sanitize_text_for_tts

logger = logging.getLogger(__name__)


class LLMPipeline:
    """Orchestrates Gemini LLM generation for daily newsletter and podcast script."""

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            self.api_key = config.gemini_api_key
        else:
            self.api_key = api_key
        self.client = None
        if self.api_key:
            try:
                from google import genai

                self.client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client.")
            except Exception as e:
                logger.warning("Could not initialize Google GenAI client: %s", e)

    def generate_newsletter_content(
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: Optional[ShowConfig] = None,
        date_str: str = "",
    ) -> Dict[str, Any]:
        """Generate structured newsletter items from curated stories."""
        if show is None:
            show = config.get_show("edmonton")

        if not date_str:
            tz = pytz.timezone(config.timezone)
            date_str = datetime.now(tz).strftime("%A, %B %d, %Y")

        if self.client:
            try:
                return self._generate_newsletter_with_gemini(tiered_stories, show, date_str)
            except Exception as e:
                logger.warning(
                    "Gemini newsletter generation failed for '%s': %s. Using local synthesis.",
                    show.id if show else "unknown",
                    e,
                )

        return self._generate_newsletter_local_fallback(tiered_stories, show, date_str)

    def generate_podcast_script(
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: Optional[ShowConfig] = None,
        date_str: str = "",
    ) -> str:
        """Generate a single-host, conversational podcast episode script tailored to the show."""
        if show is None:
            show = config.get_show("edmonton")

        if not date_str:
            tz = pytz.timezone(config.timezone)
            date_str = datetime.now(tz).strftime("%A, %B %d, %Y")

        if self.client:
            try:
                script = self._generate_podcast_with_gemini(tiered_stories, show, date_str)
                cleaned = sanitize_text_for_tts(script)
                word_count = len(cleaned.split())
                logger.info("Generated podcast script for '%s': %d words.", show.id, word_count)
                return cleaned
            except Exception as e:
                logger.warning(
                    "Gemini podcast generation failed for '%s': %s. Using fallback script generator.",
                    show.id if show else "unknown",
                    e,
                )

        script = self._generate_podcast_local_fallback(tiered_stories, show, date_str)
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
            "oilers": "EDMONTON OILERS NEWS & ANALYSIS",
            "pacific_canadian": "PACIFIC DIVISION & CANADIAN RIVALS (FLAMES, CANUCKS)",
            "nhl_league": "AROUND THE NHL & LEAGUE HEADLINES",
            "frontier_models": "FRONTIER AI MODELS & RESEARCH BREAKTHROUGHS",
            "clinical_health_ai": "AI IN HEALTHCARE, MEDICINE & CLINICAL DEPLOYMENTS",
            "compute_and_industry": "COMPUTE INFRASTRUCTURE, SEMICONDUCTORS & VENTURE",
            "policy_and_society": "AI POLICY, GOVERNANCE & GLOBAL ADOPTION",
        }
        for tier, stories in tiered_stories.items():
            label = tier_labels.get(tier, tier.replace("_", " ").upper())
            lines.append(f"\n--- {label} ---")
            for i, s in enumerate(stories, 1):
                lines.append(f"{i}. Title: {s.title}")
                lines.append(f"   Summary: {s.summary}")
                lines.append(f"   Source: {s.source} ({s.published_str})")
        return "\n".join(lines)

    def _get_show_prompt(
        self, show: ShowConfig, context: str, date_str: str
    ) -> str:
        """Construct a tailored system prompt and narrative arc based on show persona."""
        target_words = show.target_words

        if show.prompt_type == "oilers_hockey":
            prompt = f"""You are an enthusiastic, articulate, deeply knowledgeable hockey broadcaster and analyst hosting today's edition of '{show.title}' for {date_str}.

You are speaking directly to passionate hockey fans across Oil Country and the entire NHL community.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,200 to 1,400 words). This represents approximately 8 to 10 minutes of spoken audio at standard broadcast pace.

STRUCTURE & TOPICS:
1. High-Energy Intro: Welcome listeners to the show, state today's date ({date_str}), set an energetic tone, and tease today's top Oilers storylines, Pacific Division matchups, and NHL headlines.
2. Edmonton Oilers Spotlight: Deep dive into the Oilers news. Discuss training camp, recent games, line chemistry (McDavid, Draisaitl, top six, defensive pairings), goaltending, coach Kris Knoblauch's tactics, and upcoming matchups at Rogers Place. Use authentic hockey terms (forecheck, cycle, special teams, five-on-five, breakout).
3. Pacific Division & Canadian Rivals: Breakdown news and rivalry chatter concerning the Calgary Flames, Vancouver Canucks, and the Pacific Division playoff picture.
4. Around the NHL: Scan the wider league for major trades, waiver claims, Calder trophy rookie race, injury bulletins, or standout highlights.
5. Outro: Summarize key games to watch tonight, deliver a sharp final thought, and sign off with a warm, energetic send-off for Oil Country.

AUDIO & SPOKEN STYLE RULES (CRITICAL):
- This script will be read directly by an AI Text-To-Speech engine.
- Write in 100% natural, spoken, conversational English.
- DO NOT include ANY markdown syntax (no asterisks, no hash signs, no bullet points).
- DO NOT include ANY bracketed stage directions such as [Music], [Cheering], [Host laughs], or (Pause). Every single word in your output will be spoken aloud.
- Use natural spoken transitions: "Turning our attention to the blue line...", "Down south in Calgary...", "Looking around the league today..."

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""
        elif show.prompt_type == "global_ai":
            prompt = f"""You are a lucid, sophisticated, intellectually rigorous technology analyst hosting today's episode of '{show.title}' for {date_str}.

Your audience includes physicians, technologists, researchers, and builders who appreciate depth, substance, and zero marketing hype.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,200 to 1,400 words). This represents approximately 8 to 10 minutes of spoken audio.

STRUCTURE & TOPICS:
1. Thoughtful Intro: Welcome listeners, state today's date ({date_str}), and frame the conceptual theme connecting today's AI developments.
2. Frontier Models & Research: Dive into the latest foundation models, multi-modal reasoning breakthroughs, context architecture, and agentic benchmarks. Explain *how* they work and what makes them functionally significant.
3. AI in Healthcare & Medicine: Provide nuanced, clinically grounded analysis of medical AI applications—diagnostic radiology/pathology, clinical documentation assistants, pharmacology/drug discovery models, and hospital deployment realities.
4. Compute, Infrastructure & Industry: Examine the physical backbone of AI—hyperscaler data centers, NVIDIA GPUs, custom silicon ASICs, energy constraints, and major venture investments.
5. Policy, Safety & Global Governance: Discuss regulatory frameworks, open-weights debates, safety auditing, copyright rulings, and societal adoption.
6. Outro: Synthesize the broader implications of today's developments and deliver an articulate, memorable concluding sign-off.

AUDIO & SPOKEN STYLE RULES (CRITICAL):
- This script will be read directly by an AI Text-To-Speech engine.
- Write in 100% natural, spoken, conversational English.
- DO NOT include ANY markdown syntax (no asterisks, no hash signs, no bullet points).
- DO NOT include ANY bracketed stage directions such as [Intro Fades], [Pause], or (Music). Every single word in your output will be spoken aloud.
- Use natural spoken transitions: "Now exploring clinical applications...", "On the hardware and semiconductor front...", "Shifting to policy and global governance..."

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""
        else:  # Default: edmonton_news
            prompt = f"""You are an engaging, articulate, professional podcast host delivering today's comprehensive morning briefing for '{show.title}' on {date_str}.

You are speaking directly to a listener over coffee or during their morning commute in Edmonton, Alberta.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,300 to 1,500 words). This represents approximately 10 minutes of spoken audio at standard conversation pace.

STRUCTURE & TOPICS:
1. Warm Intro: Welcome the listener, state today's date ({date_str}), and preview the journey ahead from our backyard in Edmonton, across Alberta, into Canada as a whole, and out to major global developments.
2. Edmonton Local News: Dive in-depth into the local stories. Give meaningful context—why it matters to Edmontonians, transit riders, families, or local businesses.
3. Alberta Provincial News: Transition smoothly to the provincial picture. Discuss policy, healthcare, energy, economy, or government developments with nuanced analysis.
4. Canada National News: Expand our lens to federal politics, the national economy, interest rates, or cross-country affairs.
5. Global / World News: Connect Canadian and local listeners to major international headlines, geopolitical movements, or groundbreaking events.
6. Outro: Summarize key takeaways, offer an inspiring or thoughtful concluding thought for the day, and deliver a warm sign-off.

AUDIO & SPOKEN STYLE RULES (CRITICAL):
- This script will be read directly by an AI Text-To-Speech engine.
- Write in 100% natural, spoken, conversational English.
- DO NOT include ANY markdown syntax (no asterisks, no hash signs, no bullet points).
- DO NOT include ANY bracketed stage directions such as [Music], [Pause], or (Host smiles). Every single word in your output will be spoken aloud.
- Use natural spoken transitions: "Turning to our provincial beat...", "Looking across the country...", "Shifting our view across the border..."

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""
        return prompt

    def _generate_newsletter_with_gemini(
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: ShowConfig,
        date_str: str,
    ) -> Dict[str, Any]:
        """Invoke Gemini to generate structured JSON newsletter content."""
        context = self._format_stories_prompt_context(tiered_stories)

        prompt = f"""You are an expert news editor producing a daily intelligence newsletter for '{show.title}' on {date_str}.

Analyze the curated stories below across all categories and produce a structured JSON response.

Return ONLY valid JSON adhering strictly to this schema:
{{
  "date": "{date_str}",
  "summary_lead": "A 2-3 sentence executive morning summary capturing today's major themes.",
  "tiers": {{
    "<tier_name>": [
      {{
        "headline": "Punchy, accurate headline (maximum 12 words)",
        "context": "2 to 3 concise, informative sentences of essential context and significance.",
        "source": "Source publication name",
        "link": "Full URL to original article"
      }}
    ]
  }}
}}

Stories Context:
{context}
"""

        candidate_models = ["gemini-flash-latest", "gemini-3.6-flash"]
        text_response = ""
        last_error = None

        for model_name in candidate_models:
            try:
                res = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text_response = res.text or ""
                if text_response:
                    break
            except Exception as e:
                last_error = e
                try:
                    interaction = self.client.interactions.create(
                        model=model_name,
                        input=prompt,
                    )
                    text_response = interaction.output_text or ""
                    if text_response:
                        break
                except Exception as e2:
                    last_error = e2

        if not text_response:
            raise RuntimeError(f"All Gemini candidate models failed: {last_error}")

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
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: ShowConfig,
        date_str: str,
    ) -> str:
        """Invoke Gemini to write a conversational podcast script for the specified show."""
        context = self._format_stories_prompt_context(tiered_stories)
        prompt = self._get_show_prompt(show, context, date_str)

        candidate_models = ["gemini-flash-latest", "gemini-3.6-flash"]
        text_response = ""
        last_error = None

        for model_name in candidate_models:
            try:
                res = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text_response = res.text or ""
                if text_response:
                    break
            except Exception as e:
                last_error = e
                try:
                    interaction = self.client.interactions.create(
                        model=model_name,
                        input=prompt,
                    )
                    text_response = interaction.output_text or ""
                    if text_response:
                        break
                except Exception as e2:
                    last_error = e2

        if not text_response:
            raise RuntimeError(f"All Gemini candidate models failed: {last_error}")

        return text_response

    def _generate_newsletter_local_fallback(
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: ShowConfig,
        date_str: str,
    ) -> Dict[str, Any]:
        """Local fallback to format stories into newsletter data structure."""
        newsletter_data: Dict[str, Any] = {
            "date": date_str,
            "summary_lead": (
                f"Welcome to your curated daily briefing for {show.title} on {date_str}. "
                "Here are the top stories shaping today's intelligence report."
            ),
            "tiers": {},
        }

        for tier, stories in tiered_stories.items():
            newsletter_data["tiers"][tier] = []
            for s in stories:
                context_sentences = s.summary.strip()
                if not context_sentences:
                    context_sentences = f"Key development reported by {s.source} regarding {s.title}."
                newsletter_data["tiers"][tier].append(
                    {
                        "headline": s.title,
                        "context": context_sentences,
                        "source": s.source,
                        "link": s.link,
                    }
                )

        return newsletter_data

    def _generate_podcast_local_fallback(
        self,
        tiered_stories: Dict[str, List[NewsStory]],
        show: ShowConfig,
        date_str: str,
    ) -> str:
        """Local fallback generating rich conversational script without external API."""
        paragraphs: List[str] = []

        if show.prompt_type == "oilers_hockey":
            paragraphs.append(
                f"Welcome to {show.title} for {date_str}. I am Dr. Nikhil Shah, and today we are "
                f"breaking down everything happening on and off the ice for the Edmonton Oilers and across the National Hockey League."
            )
        elif show.prompt_type == "global_ai":
            paragraphs.append(
                f"Welcome to {show.title} for {date_str}. I am Dr. Nikhil Shah, and today we examine the frontier of "
                f"artificial intelligence, from breakthrough neural architectures to transformative clinical healthcare applications."
            )
        else:
            paragraphs.append(
                f"Good morning and welcome to {show.title} for {date_str}. I am Dr. Nikhil Shah, "
                f"delivering your morning intelligence briefing covering Edmonton, Alberta, Canada, and key global headlines."
            )

        for tier, stories in tiered_stories.items():
            tier_name = tier.replace("_", " ").title()
            paragraphs.append(
                f"Now turning our focus directly to {tier_name}. There are several essential developments "
                "that deserve our attention and careful analysis today."
            )
            for s in stories:
                paragraphs.append(
                    f"First on our radar: {s.title}. As reported by {s.source}, {s.summary} "
                    f"Looking more deeply into this headline, the broader implications are substantial for our community. "
                    f"Whether we examine the economic trajectory, community impact, or governance perspective, "
                    f"this development signals important momentum across {tier_name}. Analysts and observers will continue "
                    "monitoring upcoming milestones as further details unfold in the coming days."
                )

        paragraphs.append(
            f"That wraps up today's comprehensive edition of {show.title} for {date_str}. "
            "Thank you so much for joining me this morning. Be sure to stay informed, take care of those around you, "
            "and have a productive and fantastic day ahead."
        )

        return "\n\n".join(paragraphs)
