"""LLM pipeline for generating structured newsletters and conversational podcast scripts across shows."""

import json
import logging
import re
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
            prompt = f"""You are an energetic, witty, deeply knowledgeable hockey broadcaster and analyst hosting '{show.title}' for {date_str}.

You are speaking directly to passionate hockey fans across Oil Country and the entire N.H.L. community.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,200 to 1,400 words). This represents approximately 8 to 10 minutes of spoken audio at broadcast pace.

TONE & BROADCAST STYLE:
- High energy, passionate, fun, authentic morning hockey talk! Think engaging sports radio or top hockey podcast.
- Rich hockey vernacular: forecheck, heavy cycle down low, five-on-five, breakout, gap control, blue line, saucer pass, high-danger chances.
- Celebrate Connor McDavid and Leon Draisaitl's wizardry, analyze Kris Knoblauch's tactics, and bring genuine excitement.
- Keep the narrative lively, witty, and fun—banter, sharp observations, and genuine hockey love!

CRITICAL NEGATIVE RULES & TTS FORMATTING:
- NEVER introduce yourself as Dr. Nikhil Shah or say "I am Dr. Nikhil Shah" or "This is Dr. Nikhil Shah". You are simply the host of the show.
- NEVER use repetitive transition formulas like "First on our radar", "On our radar", "Now turning our focus to", or "Shifting our attention to". Vary your transitions completely.
- ALWAYS write "A.I." with periods (never bare "AI") so speech synthesizers don't say "eye".
- ALWAYS write "N.H.L." with periods.
- FACT CHECK: Kris Knoblauch is the head coach of the Edmonton Oilers (NOT Mike Babcock). Connor McDavid is captain. Do not invent coaching or management changes.
- NO markdown (no asterisks, no hashes, no bullets). NO bracketed cues like [Music] or (laughs). Every single word in your output will be spoken aloud.

STRUCTURE:
1. Energetic Cold Open: Welcome hockey fans to {show.title} for {date_str}, hype up the morning energy, and preview today's storylines.
2. Edmonton Oilers Spotlight: Deep dive into the Oilers. Training camp, line chemistry, coaching strategies from Kris Knoblauch, goaltending battles, and expectations at Rogers Place.
3. Pacific Division & Canadian Rivals: Calgary Flames, Vancouver Canucks, and division rivalry banter.
4. Around the N.H.L.: League-wide trades, rookie watch, and storylines.
5. Outro: Fun final sign-off for Oil Country.

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""
        elif show.prompt_type == "global_ai":
            prompt = f"""You are a captivating, witty, intellectually curious technology specialist hosting '{show.title}' for {date_str}.

Your audience loves discovering breakthroughs in artificial intelligence, clinical medicine, and cutting-edge hardware without dry corporate jargon or marketing fluff.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,200 to 1,400 words). This represents approximately 8 to 10 minutes of spoken audio.

TONE & BROADCAST STYLE:
- Engaging, enthusiastic, insightful, and FUN! Explain mind-blowing concepts with vivid, clear analogies.
- Treat listeners like smart peers. Connect the dots between raw research and practical impact in hospitals, labs, and daily life.
- Avoid repetitive, monotonous sentence structures. Make every topic feel fresh and fascinating.

CRITICAL NEGATIVE RULES & TTS FORMATTING:
- NEVER introduce yourself as Dr. Nikhil Shah or say "I am Dr. Nikhil Shah" or "This is Dr. Nikhil Shah". You are simply the host of the show.
- NEVER use repetitive transition formulas like "First on our radar", "On our radar", "Now turning our focus to", or "Shifting our attention to".
- ALWAYS write "A.I." with periods (A.I.) whenever mentioning artificial intelligence. NEVER write bare "AI" because speech engines will mispronounce it as "eye".
- ALWAYS write "G.P.U." / "G.P.U.s" and "L.L.M." / "L.L.M.s" with periods.
- NO markdown (no asterisks, no hashes, no bullets). NO bracketed cues like [Music] or (chuckles). Every single word in your output will be spoken aloud.

STRUCTURE:
1. Intriguing Open: Welcome listeners to {show.title} for {date_str}. Tease the big ideas on today's docket.
2. Frontier Models & Research: Latest foundation models, reasoning, multimodal tools. Explain how they work in a captivating way.
3. A.I. in Healthcare & Clinical Medicine: Medical diagnostics, pathology, radiology, ambient clinical scribes, and hospital realities.
4. Compute, Silicon & Infrastructure: Data centers, custom silicon, energy constraints, and the massive hardware race.
5. Governance, Safety & Global Impact: Policy, safety debates, open weights, and societal shifts.
6. Outro: Thought-provoking concluding thought and a warm sign-off.

Today's Curated Stories:
{context}

Begin the podcast episode directly with the host's spoken words:
"""
        else:  # Default: edmonton_news
            prompt = f"""You are a friendly, witty, articulate morning podcast host delivering '{show.title}' on {date_str}.

You are speaking to listeners over morning coffee or during their daily commute down the Whitemud or Anthony Henday in Edmonton, Alberta.

TARGET LENGTH: Exactly {target_words} words (acceptable range: 1,300 to 1,500 words). Approximately 10 minutes spoken.

TONE & BROADCAST STYLE:
- Warm, observant, witty, and engaging. Like your favorite morning radio voice who feels like an authentic Edmonton neighbour.
- Fast-paced and conversational. Avoid stiff, robotic recitations or repetitive filler.

CRITICAL NEGATIVE RULES & TTS FORMATTING:
- NEVER introduce yourself as Dr. Nikhil Shah or say "I am Dr. Nikhil Shah" or "This is Dr. Nikhil Shah". You are simply the host of the show.
- NEVER use repetitive transition formulas like "First on our radar", "On our radar", "Now turning our focus to", or "Shifting our attention to". Vary your transitions completely.
- ALWAYS write "A.I." with periods (never bare "AI") so the speech engine pronounces both letters rather than saying "eye".
- ALWAYS write "L.R.T.", "C.B.C.", "N.H.L." with periods.
- FACT CHECK:
  * Prime Minister of Canada is Justin Trudeau (NOT Mark Carney).
  * Edmonton Oilers head coach is Kris Knoblauch (NOT Mike Babcock).
  * Premier of Alberta is Danielle Smith.
  * Mayor of Edmonton is Amarjeet Sohi.
- NO markdown (no asterisks, no hashes, no bullets). NO bracketed cues like [Music] or (Pause). Every single word in your output will be spoken aloud.

STRUCTURE:
1. Warm Morning Welcome: Greet Edmonton on {date_str}, acknowledge the morning commute/weather, and tease the journey.
2. Edmonton Local Scene: Transit, city developments, community stories, and local pulse.
3. Alberta Provincial Beat: Healthcare, economy, energy, and policy across the province.
4. Canada National News: Federal affairs, national economy, and cross-country headlines.
5. Global Headlines: International events and their ripple effects back home.
6. Outro: Uplifting, warm sign-off to start the day right.

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

        candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
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

        candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
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
                f"Welcome to your daily briefing for {show.title} on {date_str}. "
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
                f"Welcome hockey fans to {show.title} for {date_str}! Grab your morning coffee, because "
                "training camp is in full swing and we have an incredible lineup of hockey talk to break down today."
            )
            paragraphs.append(
                "Around Rogers Place, the energy is pure electricity as the Edmonton Oilers ramp up on-ice preparations. "
                "Head coach Kris Knoblauch is setting a blistering pace in practice, zeroing in on high-tempo breakouts, "
                "tight gap control on the blue line, and offensive zone chemistry between Connor McDavid and Leon Draisaitl."
            )
        elif show.prompt_type == "global_ai":
            paragraphs.append(
                f"Welcome to {show.title} for {date_str}! Today we are tracking the most fascinating moves across "
                "artificial intelligence, from breakthrough foundation models to clinical healthcare tools and massive compute infrastructure."
            )
            paragraphs.append(
                "In our top research headlines, labs are pushing the envelope with next-generation multimodal reasoning and distilled open-weight architectures, "
                "making advanced cognitive capabilities accessible across standard consumer hardware."
            )
        else:
            paragraphs.append(
                f"Good morning, Edmonton! Welcome to {show.title} for {date_str}. Whether you are grabbing your first cup of coffee "
                "or navigating the morning commute, it is great to have you with us today as we tour through our city, our province, and the wider world."
            )
            paragraphs.append(
                "Starting right here in Edmonton, city teams and local organizations are advancing key infrastructure priorities, "
                "transit expansions, and community enrichment initiatives across our neighbourhoods."
            )

        # Dynamic varied narrative paragraphs per tier
        transition_starters = [
            "Digging into our next story,",
            "Meanwhile, another development catching attention across the region,",
            "Expanding our perspective further,",
            "Also making news across the wire today,",
            "Taking a look across another key front,",
            "Switching gears to our next highlight,",
            "In other notable developments,",
            "Turning next to an interesting update,",
        ]
        tier_takes = {
            "edmonton": [
                "It is always encouraging to see local municipal teams and community partners driving tangible progress across our neighbourhoods. As implementation ramps up, Edmontonians will see direct benefits in service accessibility and daily life.",
                "This will definitely be a project that local residents, commuters, and city leaders will be following closely as the season unfolds. The next few weeks will shed light on delivery timelines and community feedback.",
                "Stories like this underscore how quickly Edmonton continues to evolve across infrastructure, culture, and community life. We will keep tabs on council discussions and regional milestones as things progress.",
            ],
            "alberta": [
                "Across the province, conversations are heating up around economic competitiveness and regional priorities. Municipal leaders and business groups are emphasizing the need for balanced growth.",
                "Provincial observers and civic leaders will be watching closely to see how these policy shifts deliver on the ground. The practical outcomes over the coming quarter will be closely scrutinized.",
                "It reflects broader provincial dynamics that will likely remain front and centre through the coming months. Stay tuned as provincial stakeholders release further updates.",
            ],
            "canada": [
                "At the national level, policymakers are balancing competing economic factors and cross-country priorities. Finding consensus across regional economies will remain a core challenge for Ottawa.",
                "This carries meaningful ripple effects for Canadian households, businesses, and communities from coast to coast. Federal committees are scheduled to review detailed implementation plans shortly.",
                "Federal observers are weighing how quickly these commitments will turn into concrete results over the coming quarter. It highlights the delicate balance of national strategy and practical delivery.",
            ],
            "world": [
                "On the global stage, diplomatic and economic ripples are being felt well beyond international borders. International partners and trade allies are closely monitoring diplomatic channels.",
                "Global markets and international partners are keeping a watchful eye on how these regional negotiations unfold. Key delegations are expected to convene again before the end of the month.",
                "It serves as a vivid reminder of how closely our domestic concerns connect to broader international currents. We will track foreign ministry briefings and international coverage as details emerge.",
            ],
            "oilers": [
                "The buzz around Rogers Place is electric, and fans are eager to see this talent translate to opening night dominance. The coaching staff is hammering home defensive accountability.",
                "Kris Knoblauch and his coaching staff are dialing in tactical discipline, setting high expectations right out of the gate. Special teams execution and five-on-five possession look razor-sharp.",
                "With leadership from Connor McDavid and Leon Draisaitl, the locker room focus is locked squarely on championship contention. Oil Country is ready for another unforgettable playoff push.",
            ],
            "pacific_canadian": [
                "Pacific division rivalries never take a night off, and every point in the standings will be hard-fought this year. Expect fast-paced, high-stakes hockey every time the division rivals collide.",
                "Matchups against Canadian rivals like Calgary and Vancouver are guaranteed to bring playoff-level intensity. Both rival rosters have made major off-season adjustments to match our speed.",
            ],
            "nhl_league": [
                "Across the wider N.H.L., rosters are taking final shape as preseason camps push players to their limits. Front offices are finalizing their cap configurations and waiver decisions.",
                "Analysts are already projecting a razor-thin playoff race across both conferences as opening week approaches. Veteran leadership and goaltending depth will likely make all the difference.",
            ],
            "frontier_models": [
                "The velocity of foundational model research continues to accelerate, especially in multi-step reasoning and parameter efficiency. Research labs are proving that disciplined architectural design beats raw compute scale.",
                "Optimized distillation and open-weight architectures are democratizing advanced intelligence for researchers worldwide. It is remarkable to see state-of-the-art capabilities running on accessible hardware.",
            ],
            "clinical_health_ai": [
                "In healthcare, the clinical emphasis remains squarely on safety, validation, and easing administrative burden on physicians. Clinical trials and real-world hospital studies are establishing critical safety baselines.",
                "Clinical researchers are seeing firsthand how assistive tools can streamline diagnostic workflows while keeping clinicians firmly in control. Patient safety and interpretive accuracy remain the ultimate benchmarks.",
            ],
            "compute_and_industry": [
                "Silicon scaling, specialized accelerators, and power grid constraints remain the critical engineering bottlenecks shaping hardware innovation. Massive capital investment is pouring into energy-efficient semiconductor architectures.",
                "From custom chips to hyperscale data centre infrastructure, capital investment is reshaping global technology capacity. Industry leaders are planning multi-gigawatt facilities to meet escalating compute demand.",
            ],
            "policy_and_society": [
                "Governance frameworks and safety benchmarks are maturing rapidly as international standards begin to solidify. International working groups are aligning on evaluation metrics and transparency standards.",
                "Finding the right balance between open innovation and responsible deployment continues to drive productive global discussions. Regulatory bodies are working closely with industry researchers to craft sound policies.",
            ],
        }

        t_idx = 0
        take_counters = {}

        for tier, stories in tiered_stories.items():
            takes = tier_takes.get(tier, [
                "Observers and stakeholders will be keeping a close eye on further milestones as this story continues to develop.",
                "This remains an evolving storyline that analysts and the public will be tracking over the days ahead.",
            ])
            for s in stories:
                lead_in = transition_starters[t_idx % len(transition_starters)]
                t_idx += 1
                c_idx = take_counters.get(tier, 0)
                closing_take = takes[c_idx % len(takes)]
                take_counters[tier] = c_idx + 1

                cleaned_title = s.title.replace("AI", "A.I.").replace("NHL", "N.H.L.")
                cleaned_summary = s.summary.replace("AI", "A.I.").replace("NHL", "N.H.L.")
                paragraphs.append(
                    f"{lead_in} {cleaned_title}. According to reporting from {s.source}, {cleaned_summary} "
                    f"{closing_take}"
                )

        if show.prompt_type == "oilers_hockey":
            paragraphs.append(
                f"That wraps up today's edition of {show.title}. Enjoy the camp highlights, stay loud, and let's go Oilers!"
            )
        elif show.prompt_type == "global_ai":
            paragraphs.append(
                f"That is your briefing on {show.title} for {date_str}. Thank you for listening, and have an inspiring day ahead."
            )
        else:
            paragraphs.append(
                f"That brings us to the end of today's morning briefing on {show.title} for {date_str}. "
                "Have a safe, productive, and wonderful day ahead in Edmonton!"
            )

        return "\n\n".join(paragraphs)
