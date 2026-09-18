"""Main orchestrator and CLI entry point for PodCow Multi-Podcast Network."""

import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import pytz

import utils.audio_utils
from config import config, ShowConfig
from collectors.news_collector import NewsCollector
from generators.llm_pipeline import LLMPipeline
from generators.tts_synthesizer import TTSSynthesizer
from generators.podcast_feed import PodcastFeedManager
from deliverers.mailer import Mailer
from utils.cover_art import generate_all_covers

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


def run_show(
    show: ShowConfig,
    dry_run: bool = False,
    stories_per_tier: int = 3,
    send_email: bool = False,
) -> bool:
    """Execute the end-to-end pipeline for an individual podcast show."""
    tz = pytz.timezone(config.timezone)
    now_local = datetime.now(tz)
    datestamp = now_local.strftime("%Y%m%d")
    date_display = now_local.strftime("%A, %B %d, %Y")

    print("\n" + "=" * 70)
    print(f" SHOW: {show.title.upper()}")
    print(f" Category: {show.category} / {show.subcategory} | Voice: {show.voice_name}")
    print(f" Execution Time: {now_local.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print(f" Mode: {'DRY RUN (Preview Only)' if dry_run else 'PRODUCTION RUN'}")
    print("=" * 70 + "\n")

    # Step 1: Collect News
    logger.info("--- [%s] Step 1: Collecting Curated News ---", show.id)
    collector = NewsCollector(request_timeout=8)
    tiered_stories = collector.fetch_show_tiers(show, stories_per_tier=stories_per_tier)

    total_stories = sum(len(s) for s in tiered_stories.values())
    logger.info("[%s] Total curated stories gathered: %d", show.id, total_stories)
    for tier, stories in tiered_stories.items():
        print(f"  [{tier.upper()}] {len(stories)} stories gathered.")

    # Step 2: Content Generation (Newsletter & Podcast Script)
    logger.info("--- [%s] Step 2: Generating Script via Gemini ---", show.id)
    llm = LLMPipeline()

    newsletter_data = llm.generate_newsletter_content(
        tiered_stories, show=show, date_str=date_display
    )

    podcast_script = llm.generate_podcast_script(
        tiered_stories, show=show, date_str=date_display
    )
    word_count = len(podcast_script.split())
    logger.info("[%s] Podcast script generated: %d words.", show.id, word_count)

    script_file = config.output_dir / f"{show.id}_script_{datestamp}.txt"
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(podcast_script)
    logger.info("[%s] Saved podcast script to: %s", show.id, script_file)

    # Step 3: Audio Synthesis
    logger.info("--- [%s] Step 3: Synthesizing Audio (Voice: %s) ---", show.id, show.voice_name)
    mp3_filename = f"{show.id}_{datestamp}.mp3"
    # Keep legacy naming podcast_YYYYMMDD.mp3 for Edmonton to avoid breaking prior feeds
    if show.id == "edmonton":
        mp3_filename = f"podcast_{datestamp}.mp3"

    mp3_path = config.output_dir / mp3_filename
    if dry_run:
        logger.info("[%s] Dry run mode: skipping audio synthesis.", show.id)
    else:
        synthesizer = TTSSynthesizer(voice_name=show.voice_name)
        try:
            mp3_path = synthesizer.synthesize_script_to_mp3(
                script_text=podcast_script,
                output_path=mp3_path,
                date_str=datestamp,
            )
            logger.info("[%s] Audio synthesis complete: %s", show.id, mp3_path)
        except Exception as e:
            logger.error("[%s] Audio synthesis encountered an error: %s", show.id, e)
            raise

    # Step 4: Update Podcast RSS Feed
    logger.info("--- [%s] Step 4: Updating Podcast Feed XML ---", show.id)
    feed_mgr = PodcastFeedManager.for_show(show)
    filesize = mp3_path.stat().st_size if (mp3_path and mp3_path.exists()) else 0
    duration_secs = int((word_count / 145) * 60)
    feed_path = feed_mgr.add_or_update_episode(
        date_str=date_display,
        datestamp=datestamp,
        mp3_filename=mp3_filename,
        mp3_filesize=filesize,
        duration_seconds=duration_secs,
        summary_html=newsletter_data.get("summary_lead", ""),
    )
    logger.info("[%s] Podcast RSS feed updated at: %s", show.id, feed_path)

    # Step 5: Email Delivery (Optional, only if requested or default edmonton)
    delivery_success = True
    if send_email:
        logger.info("--- [%s] Step 5: Delivering Email ---", show.id)
        mailer = Mailer()
        delivery_success = mailer.send_daily_briefing(
            newsletter_data=newsletter_data,
            mp3_path=mp3_path,
            dry_run=dry_run,
        )

    feed_url = f"{config.base_url}/{show.feed_filename}"
    print("\n" + "-" * 70)
    print(f" [{show.title}] COMPLETED")
    print(f"  - Words Spoken: {word_count} (~{word_count / 145:.1f} mins)")
    if mp3_path and mp3_path.exists():
        print(f"  - Audio MP3: {mp3_path} ({mp3_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"  - Feed XML: {feed_path}")
    print(f"  - Pocket Casts URL: {feed_url}")
    print("-" * 70 + "\n")

    return delivery_success


def run_pipeline(
    show_target: str = "all",
    dry_run: bool = False,
    stories_per_tier: int = 3,
    send_email: bool = True,
) -> bool:
    """Execute pipeline for one or all shows."""
    if show_target == "all":
        target_shows = list(config.shows.values())
    else:
        show = config.get_show(show_target)
        if not show:
            print(f"Error: Unknown show '{show_target}'. Available: {list(config.shows.keys())}")
            return False
        target_shows = [show]

    all_success = True
    for show in target_shows:
        # Only email the primary Edmonton news show by default to avoid flooding user's inbox
        should_email = send_email and (show.id == "edmonton")
        success = run_show(
            show=show,
            dry_run=dry_run,
            stories_per_tier=stories_per_tier,
            send_email=should_email,
        )
        if not success:
            all_success = False

    print("\n" + "=" * 70)
    print(" ALL SHOWS PROCESSED")
    print(" Subscribe in Pocket Casts via Search:")
    for show in config.shows.values():
        print(f"  - {show.title}: {config.base_url}/{show.feed_filename}")
    print("=" * 70 + "\n")

    return all_success


def test_news_retrieval(show_target: str = "all"):
    """CLI utility to test and inspect RSS news retrieval."""
    collector = NewsCollector()
    target_shows = config.shows.values() if show_target == "all" else [config.get_show(show_target)]

    for show in target_shows:
        if not show:
            continue
        print(f"\n=======================================================")
        print(f" TESTING NEWS FOR SHOW: {show.title.upper()}")
        print(f"=======================================================")
        tiered = collector.fetch_show_tiers(show, stories_per_tier=2)
        for tier, stories in tiered.items():
            print(f"\n--- Tier: {tier.upper()} ({len(stories)} stories) ---")
            for i, s in enumerate(stories, 1):
                print(f"  {i}. [{s.source}] {s.title}")
                print(f"     URL: {s.link}")


def start_scheduler():
    """Start APScheduler to run all shows automatically every morning at 7:00 AM Mountain Time."""
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
        kwargs={"show_target": "all", "dry_run": False},
        id="podcow_daily_shows_job",
        name="PodCow Daily Podcast Network",
        replace_existing=True,
    )

    print(f"\n[SCHEDULER] PodCow Daily Podcast Network started.")
    print(f"[SCHEDULER] Scheduled to run every day at {hour:02d}:{minute:02d} ({config.timezone}).")
    print(f"[SCHEDULER] Shows: {', '.join(s.title for s in config.shows.values())}")
    print(f"[SCHEDULER] Press Ctrl+C to exit.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n[SCHEDULER] Stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="PodCow Multi-Podcast Network Generator & Automation Service"
    )
    parser.add_argument(
        "--show",
        choices=["all", "edmonton", "oilers", "ai"],
        default="all",
        help="Specify which podcast show to execute (default: all).",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately (end-to-end production run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pipeline in preview mode (tests collection, scripts, and feeds without live delivery).",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the automated daily scheduler (7:00 AM Mountain Time).",
    )
    parser.add_argument(
        "--test-news",
        action="store_true",
        help="Fetch and display top news stories for the specified show.",
    )
    parser.add_argument(
        "--generate-covers",
        action="store_true",
        help="Generate high-resolution 1400x1400 cover art images for all shows.",
    )
    parser.add_argument(
        "--stories-per-tier",
        type=int,
        default=3,
        help="Number of stories to curate per tier (default: 3).",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email delivery step (useful when listening exclusively via Pocket Casts).",
    )

    args = parser.parse_args()

    if args.generate_covers:
        generate_all_covers()
    elif args.test_news:
        test_news_retrieval(show_target=args.show)
    elif args.dry_run:
        run_pipeline(
            show_target=args.show,
            dry_run=True,
            stories_per_tier=args.stories_per_tier,
            send_email=not args.no_email,
        )
    elif args.run_now:
        run_pipeline(
            show_target=args.show,
            dry_run=False,
            stories_per_tier=args.stories_per_tier,
            send_email=not args.no_email,
        )
    elif args.schedule:
        start_scheduler()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
