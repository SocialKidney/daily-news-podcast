"""Email delivery module for sending HTML newsletters with MP3 podcast attachments via SMTP."""

import os
import smtplib
import logging
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader

from config import config

logger = logging.getLogger(__name__)


class Mailer:
    """Handles rendering and delivering daily HTML newsletters and podcast audio attachments."""

    def __init__(self):
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir), autoescape=True
        )
        self.template = self.jinja_env.get_template("newsletter.html")

    def render_html(
        self, newsletter_data: Dict[str, Any], podcast_filename: str = ""
    ) -> str:
        """Render newsletter HTML from data dictionary."""
        context = {**newsletter_data, "podcast_filename": podcast_filename}
        return self.template.render(context)

    def render_plain_text(self, newsletter_data: Dict[str, Any]) -> str:
        """Generate a clean plain-text version of the briefing."""
        date_str = newsletter_data.get("date", "")
        lines = [
            f"DAILY BRIEFING & PODCAST - {date_str}",
            "=" * 50,
            newsletter_data.get("summary_lead", ""),
            "\nNote: Today's 10-minute audio briefing is attached as an MP3.\n",
        ]

        tier_titles = {
            "edmonton": "EDMONTON LOCAL",
            "alberta": "ALBERTA PROVINCIAL",
            "canada": "CANADA NATIONAL",
            "world": "GLOBAL / WORLD",
        }

        for tier, title in tier_titles.items():
            stories = newsletter_data.get(tier, [])
            if not stories:
                continue
            lines.append(f"\n--- {title} ---")
            for s in stories:
                lines.append(f"* {s.get('headline')}")
                lines.append(f"  {s.get('context')}")
                lines.append(f"  Source: {s.get('source')} ({s.get('link')})\n")

        return "\n".join(lines)

    def send_daily_briefing(
        self,
        newsletter_data: Dict[str, Any],
        mp3_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> bool:
        """
        Deliver the daily briefing email with the MP3 attachment.
        If dry_run is True or SMTP is not configured, saves the HTML file to the output directory.
        """
        date_str = newsletter_data.get("date", "Today")
        subject = f"Daily Briefing & Podcast: {date_str} - Edmonton, Alberta, Canada & World"
        podcast_filename = mp3_path.name if mp3_path else "podcast.mp3"

        html_body = self.render_html(newsletter_data, podcast_filename=podcast_filename)
        text_body = self.render_plain_text(newsletter_data)

        # Always save local HTML archive to output directory
        datestamp = (
            mp3_path.stem.replace("podcast_", "")
            if mp3_path
            else "latest"
        )
        archive_html_path = config.output_dir / f"newsletter_{datestamp}.html"
        with open(archive_html_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        logger.info("Saved local HTML newsletter to: %s", archive_html_path)

        if dry_run:
            logger.info("Dry-run active. Skipping actual email transmission.")
            print(f"\n[DRY RUN] Email rendered successfully.")
            print(f"[DRY RUN] Subject: {subject}")
            print(f"[DRY RUN] Recipients: {config.recipient_list or ['(none specified)']}")
            print(f"[DRY RUN] HTML saved at: {archive_html_path}")
            if mp3_path and mp3_path.exists():
                print(f"[DRY RUN] MP3 attachment: {mp3_path} ({mp3_path.stat().st_size / 1024 / 1024:.2f} MB)")
            return True

        if not config.is_email_ready():
            logger.warning(
                "Email credentials or recipients not fully configured in .env. "
                "Saved output locally to %s",
                archive_html_path,
            )
            return False

        # Build MIME Message
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = config.sender_email
        msg["To"] = ", ".join(config.recipient_list)

        # Alternative container for text and HTML
        alt_container = MIMEMultipart("alternative")
        alt_container.attach(MIMEText(text_body, "plain", "utf-8"))
        alt_container.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_container)

        # Attach MP3 file if provided and exists
        if mp3_path and mp3_path.exists():
            file_size_mb = mp3_path.stat().st_size / (1024 * 1024)
            if file_size_mb > 25:
                logger.warning(
                    "MP3 file size (%.2f MB) exceeds standard 25MB email limit. "
                    "Sending email without direct attachment.",
                    file_size_mb,
                )
            else:
                try:
                    with open(mp3_path, "rb") as f:
                        part = MIMEBase("audio", "mpeg")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{mp3_path.name}"',
                    )
                    msg.attach(part)
                    logger.info("Attached MP3 file: %s (%.2f MB)", mp3_path.name, file_size_mb)
                except Exception as e:
                    logger.error("Failed to attach MP3 file: %s", e)

        # Send via SMTP
        try:
            logger.info(
                "Connecting to SMTP server %s:%d...", config.smtp_host, config.smtp_port
            )
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            server.ehlo()
            if config.smtp_port == 587:
                server.starttls()
                server.ehlo()

            server.login(config.sender_email, config.sender_app_password)
            server.sendmail(
                config.sender_email, config.recipient_list, msg.as_string()
            )
            server.quit()

            logger.info(
                "Successfully dispatched briefing email to %s",
                config.recipient_list,
            )
            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP: %s", e)
            logger.error(
                "Tip: If using Gmail, verify you generated a 16-character App Password "
                "at https://myaccount.google.com/apppasswords"
            )
            return False
