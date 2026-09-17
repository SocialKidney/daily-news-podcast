"""Main orchestrator and CLI entry point for Daily News Aggregation and Podcast Generation."""

import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path
import pytz

import utils.audio_utils
from config import config
from collectors.news_collector import NewsCollector
from generators.llm_pipeline import LLMPipeline
from generators.tts_synthesizer import TTSSynthesizer
from deliverers.mailer import Mailer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.output_dir / "briefing.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def run_pipeline(dry_run: bool = False, stories_per_tier: int = 3) -> bool:
    """
    Execute the end-to-end daily news and podcast pipeline:
    1. Collect top news across 4 tiers (Edmonton, Alberta, Canada, World).
    2. Generate structured newsletter and 10-minute conversational podcast script.
    3. Synthesize audio into MP3 using Gemini TTS / fallback audio engine.
    4. Deliver HTML newsletter and MP3 podcast attachment via SMTP.
    """
    tz = pytz.timezone(config.timezone)
    now_local = datetime.now(tz)
    datestamp = now_local.strftime("%Y%m%d")
    date_display = now_local.strftime("%A, %B %d, %Y")

    print("\n" + "=" * 65)
    print(f" DAILY BRIEFING & PODCAST SERVICE")
    print(f" Execution Time: {now_local.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print(f" Mode: {'DRY RUN (Preview Only)' if dry_run else 'PRODUCTION RUN'}")
    print("=" * 65 + "\n")

    # Step 1: Collect News
    logger.info("--- Step 1: Collecting News Across 4 Geographic Tiers ---")
    collector = NewsCollector(request_timeout=10)
    tiered_stories = collector.fetch_all_tiers(stories_per_tier=stories_per_tier)

    total_stories = sum(len(s) for s in tiered_stories.values())
    logger.info("Total curated stories collected: %d", total_stories)
    for tier, stories in tiered_stories.items():
        print(f"  [{tier.upper()}] {len(stories)} stories gathered.")

    # Step 2: Content Generation (Newsletter & Podcast Script)
    logger.info("--- Step 2: Generating Newsletter & Conversational Podcast Script ---")
    llm = LLMPipeline()

    # Generate structured newsletter
    newsletter_data = llm.generate_newsletter_content(
        tiered_stories, date_str=date_display
    )

    # Generate 1,300 to 1,500 word podcast script (~10 minutes spoken)
    podcast_script = llm.generate_podcast_script(
        tiered_stories, date_str=date_display
    )
    word_count = len(podcast_script.split())
    logger.info("Podcast script generated: %d words.", word_count)

    # Save script to output directory for transparency and auditing
    script_file = config.output_dir / f"podcast_script_{datestamp}.txt"
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(podcast_script)
    logger.info("Saved podcast script to: %s", script_file)

    # Step 3: Audio Synthesis
    logger.info("--- Step 3: Synthesizing Audio into MP3 Podcast ---")
    mp3_path = config.output_dir / f"podcast_{datestamp}.mp3"
    synthesizer = TTSSynthesizer()

    try:
        mp3_path = synthesizer.synthesize_script_to_mp3(
            script_text=podcast_script,
            output_path=mp3_path,
            date_str=datestamp,
        )
        logger.info("Audio synthesis complete: %s", mp3_path)
    except Exception as e:
        logger.error("Audio synthesis encountered an error: %s", e)
        if dry_run:
            logger.info("Dry run continuing without audio synthesis.")
            mp3_path = None
        else:
            raise

    # Step 4: Email Delivery
    logger.info("--- Step 4: Rendering & Delivering Daily Briefing ---")
    mailer = Mailer()
    delivery_success = mailer.send_daily_briefing(
        newsletter_data=newsletter_data,
        mp3_path=mp3_path,
        dry_run=dry_run,
    )

    print("\n" + "=" * 65)
    print(" PIPELINE EXECUTION SUMMARY")
    print(f"  - Status: {'COMPLETED (DRY RUN)' if dry_run else ('SUCCESS' if delivery_success else 'SAVED LOCALLY')}")
    print(f"  - Curated Stories: {total_stories}")
    print(f"  - Podcast Words: {word_count} (~{word_count / 145:.1f} mins spoken)")
    print(f"  - Script Path: {script_file}")
    if mp3_path and mp3_path.exists():
        print(f"  - Podcast Audio: {mp3_path} ({mp3_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"  - Newsletter HTML: {config.output_dir / f'newsletter_{datestamp}.html'}")
    print("=" * 65 + "\n")

    return delivery_success


def test_news_retrieval():
    """CLI utility to test and inspect RSS news retrieval across all tiers."""
    print("\nTesting News Retrieval across all 4 tiers...")
    collector = NewsCollector()
    tiered = collector.fetch_all_tiers(stories_per_tier=2)
    for tier, stories in tiered.items():
        print(f"\n==================== {tier.upper()} ====================")
        for i, s in enumerate(stories, 1):
            print(f"{i}. [{s.source}] {s.title}")
            print(f"   Published: {s.published_str}")
            print(f"   Summary: {s.summary[:140]}...")
            print(f"   URL: {s.link}")


def start_scheduler():
    """Start APScheduler to run automatically every morning at the configured Mountain Time."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched_time = config.schedule_time.split(":")
    hour = int(sched_time[0]) if len(sched_time) > 0 else 7
    minute = int(sched_time[1]) if len(sched_time) > 1 else 0

    scheduler = BlockingScheduler()
    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=pytz.timezone(config.timezone),
    )

    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        kwargs={"dry_run": False},
        id="daily_news_podcast_job",
        name="Daily News & Podcast Briefing",
        replace_existing=True,
    )

    print(f"\n[SCHEDULER] Daily News & Podcast Service started.")
    print(f"[SCHEDULER] Scheduled to run every day at {hour:02d}:{minute:02d} ({config.timezone}).")
    print(f"[SCHEDULER] Press Ctrl+C to exit.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n[SCHEDULER] Stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Daily News Aggregation, Podcast Generation & Email Delivery Service"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the full pipeline immediately (end-to-end production run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the pipeline in preview mode without sending actual email.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the automated daily scheduler (7:00 AM Mountain Time).",
    )
    parser.add_argument(
        "--test-news",
        action="store_true",
        help="Fetch and display top news stories for Edmonton, Alberta, Canada, and World.",
    )
    parser.add_argument(
        "--stories-per-tier",
        type=int,
        default=3,
        help="Number of stories to curate per geographic tier (default: 3).",
    )

    args = parser.parse_args()

    if args.test_news:
        test_news_retrieval()
    elif args.dry_run:
        run_pipeline(dry_run=True, stories_per_tier=args.stories_per_tier)
    elif args.run_now:
        run_pipeline(dry_run=False, stories_per_tier=args.stories_per_tier)
    elif args.schedule:
        start_scheduler()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
