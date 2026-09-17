"""Generate 1400x1400 podcast cover art for Pocket Casts / Apple Podcasts."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate_podcast_cover(
    title: str = "PodCOW 2",
    subtitle: str = "DAILY NEWS EDMONTON",
    category: str = "EDMONTON * ALBERTA * CANADA * WORLD",
    output_path: Path = Path("public/assets/cover.jpg"),
):
    """Create a high-resolution 1400x1400 cover art image for podcast apps."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = (1400, 1400)

    # Create dark gradient-like canvas
    img = Image.new("RGB", size, color="#0f172a")
    draw = ImageDraw.Draw(img)

    # Draw subtle modern background geometry
    # Radial glow in top right
    for r in range(700, 0, -20):
        alpha = int(35 * (1 - r / 700))
        color = (30 + alpha, 58 + alpha * 2, 138 + alpha * 2)
        draw.ellipse([800 - r, 200 - r, 800 + r, 200 + r], fill=color)

    # Accent top border
    draw.rectangle([0, 0, 1400, 24], fill="#3b82f6")

    # Outer decorative frame
    draw.rectangle([60, 60, 1340, 1340], outline="#1e293b", width=4)
    draw.rectangle([70, 70, 1330, 1330], outline="#334155", width=2)

    # Try loading default system fonts or standard sans-serif
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 130)
        font_sub = ImageFont.truetype("arialbd.ttf", 64)
        font_tag = ImageFont.truetype("arial.ttf", 36)
        font_badge = ImageFont.truetype("arialbd.ttf", 32)
    except Exception:
        # Fallback to default
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_tag = font_title
        font_badge = font_title

    # Category Pill Badge
    badge_text = "DAILY MORNING INTELLIGENCE"
    draw.rounded_rectangle([120, 240, 650, 310], radius=16, fill="#1e3a8a", outline="#60a5fa", width=2)
    draw.text((150, 255), badge_text, fill="#93c5fd", font=font_badge)

    # Main Title
    draw.text((120, 360), title, fill="#ffffff", font=font_title)

    # Accent divider line
    draw.rectangle([120, 530, 480, 542], fill="#38bdf8")

    # Subtitle
    draw.text((120, 580), subtitle, fill="#38bdf8", font=font_sub)

    # Regional scope tag
    draw.text((120, 680), category, fill="#94a3b8", font=font_tag)

    # Waveform / Audio bars visual graphic in lower section
    bar_x = 120
    bar_y_base = 1180
    heights = [60, 120, 180, 260, 190, 310, 220, 380, 290, 170, 240, 350, 210, 130, 80]
    for h in heights:
        draw.rounded_rectangle(
            [bar_x, bar_y_base - h, bar_x + 36, bar_y_base],
            radius=12,
            fill="#2563eb",
        )
        bar_x += 54

    # Host footnote
    draw.text((120, 1240), "Dr. Nikhil Shah  *  Every Morning at 7:00 AM MT", fill="#64748b", font=font_tag)

    img.save(str(output_path), "JPEG", quality=95)
    print(f"Cover art generated at: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_podcast_cover()
