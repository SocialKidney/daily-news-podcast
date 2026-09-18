"""Generate 1400x1400 podcast cover art for Pocket Casts / Apple Podcasts."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _get_fonts():
    """Helper to safely load system fonts or fallback to default."""
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 130)
        font_sub = ImageFont.truetype("arialbd.ttf", 62)
        font_tag = ImageFont.truetype("arial.ttf", 36)
        font_badge = ImageFont.truetype("arialbd.ttf", 30)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_tag = font_title
        font_badge = font_title
    return font_title, font_sub, font_tag, font_badge


def generate_edmonton_cover(output_path: Path = Path("public/assets/cover.jpg")) -> Path:
    """Generate cover art for PodCow Daily News Edmonton."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = (1400, 1400)
    img = Image.new("RGB", size, color="#0f172a")
    draw = ImageDraw.Draw(img)

    # Radial glow in top right
    for r in range(700, 0, -20):
        alpha = int(35 * (1 - r / 700))
        color = (30 + alpha, 58 + alpha * 2, 138 + alpha * 2)
        draw.ellipse([800 - r, 200 - r, 800 + r, 200 + r], fill=color)

    # Accent top border & decorative frame
    draw.rectangle([0, 0, 1400, 24], fill="#3b82f6")
    draw.rectangle([60, 60, 1340, 1340], outline="#1e293b", width=4)
    draw.rectangle([70, 70, 1330, 1330], outline="#334155", width=2)

    font_title, font_sub, font_tag, font_badge = _get_fonts()

    # Category Pill Badge
    draw.rounded_rectangle([120, 240, 660, 310], radius=16, fill="#1e3a8a", outline="#60a5fa", width=2)
    draw.text((150, 255), "DAILY MORNING INTELLIGENCE", fill="#93c5fd", font=font_badge)

    # Titles
    draw.text((120, 360), "PodCow", fill="#ffffff", font=font_title)
    draw.rectangle([120, 530, 480, 542], fill="#38bdf8")
    draw.text((120, 580), "DAILY NEWS EDMONTON", fill="#38bdf8", font=font_sub)
    draw.text((120, 680), "EDMONTON  *  ALBERTA  *  CANADA  *  WORLD", fill="#94a3b8", font=font_tag)

    # Waveform graphic
    bar_x = 120
    bar_y_base = 1180
    heights = [60, 120, 180, 260, 190, 310, 220, 380, 290, 170, 240, 350, 210, 130, 80]
    for h in heights:
        draw.rounded_rectangle([bar_x, bar_y_base - h, bar_x + 36, bar_y_base], radius=12, fill="#2563eb")
        bar_x += 54

    draw.text((120, 1240), "Dr. Nikhil Shah  *  Every Morning at 7:00 AM MT", fill="#64748b", font=font_tag)

    img.save(str(output_path), "JPEG", quality=95)
    return output_path


def generate_oilers_cover(output_path: Path = Path("public/assets/cover_oilers.jpg")) -> Path:
    """Generate cover art for Podcow Oilers and NHL Daily (Oilers Blue & Orange)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = (1400, 1400)
    # Deep midnight navy
    img = Image.new("RGB", size, color="#041e42")
    draw = ImageDraw.Draw(img)

    # Radial blaze orange glow in top right
    for r in range(650, 0, -20):
        alpha = int(40 * (1 - r / 650))
        color = (180 + alpha, 50 + int(alpha * 0.8), 10)
        draw.ellipse([850 - r, 220 - r, 850 + r, 220 + r], fill=color)

    # Oilers blaze orange accent top border
    draw.rectangle([0, 0, 1400, 24], fill="#ff4c00")
    draw.rectangle([60, 60, 1340, 1340], outline="#0c2340", width=4)
    draw.rectangle([70, 70, 1330, 1330], outline="#1e3a8a", width=2)

    font_title, font_sub, font_tag, font_badge = _get_fonts()

    # Category Pill Badge
    draw.rounded_rectangle([120, 240, 680, 310], radius=16, fill="#7f2300", outline="#ff7733", width=2)
    draw.text((150, 255), "EDMONTON OILERS & NHL HOCKEY", fill="#fed7aa", font=font_badge)

    # Titles
    draw.text((120, 360), "PodCow", fill="#ffffff", font=font_title)
    draw.rectangle([120, 530, 480, 542], fill="#ff4c00")
    draw.text((120, 580), "OILERS & NHL DAILY", fill="#ff7733", font=font_sub)
    draw.text((120, 680), "OILERS  *  PACIFIC DIVISION  *  AROUND THE NHL", fill="#cbd5e1", font=font_tag)

    # Orange and blue rhythm bars in lower section
    bar_x = 120
    bar_y_base = 1180
    heights = [70, 140, 220, 320, 240, 370, 280, 410, 310, 200, 290, 360, 250, 160, 90]
    for idx, h in enumerate(heights):
        bar_color = "#ff4c00" if idx % 2 == 0 else "#2563eb"
        draw.rounded_rectangle([bar_x, bar_y_base - h, bar_x + 36, bar_y_base], radius=12, fill=bar_color)
        bar_x += 54

    draw.text((120, 1240), "Dr. Nikhil Shah  *  Daily Hockey Intelligence", fill="#94a3b8", font=font_tag)

    img.save(str(output_path), "JPEG", quality=95)
    return output_path


def generate_ai_cover(output_path: Path = Path("public/assets/cover_ai.jpg")) -> Path:
    """Generate cover art for Podcow Global AI Daily (Cyberpunk Obsidian & Electric Cyan)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = (1400, 1400)
    # Deep midnight slate / obsidian
    img = Image.new("RGB", size, color="#070a13")
    draw = ImageDraw.Draw(img)

    # Radial electric violet / cyan glow
    for r in range(650, 0, -20):
        alpha = int(35 * (1 - r / 650))
        color = (15 + int(alpha * 1.5), 30 + alpha * 2, 70 + alpha * 3)
        draw.ellipse([850 - r, 220 - r, 850 + r, 220 + r], fill=color)

    # Electric cyan accent top border
    draw.rectangle([0, 0, 1400, 24], fill="#06b6d4")
    draw.rectangle([60, 60, 1340, 1340], outline="#0f172a", width=4)
    draw.rectangle([70, 70, 1330, 1330], outline="#1e293b", width=2)

    font_title, font_sub, font_tag, font_badge = _get_fonts()

    # Category Pill Badge
    draw.rounded_rectangle([120, 240, 690, 310], radius=16, fill="#083344", outline="#22d3ee", width=2)
    draw.text((150, 255), "FRONTIER AI, HEALTHCARE & COMPUTE", fill="#a5f3fc", font=font_badge)

    # Titles
    draw.text((120, 360), "PodCow", fill="#ffffff", font=font_title)
    draw.rectangle([120, 530, 480, 542], fill="#06b6d4")
    draw.text((120, 580), "GLOBAL AI DAILY", fill="#22d3ee", font=font_sub)
    draw.text((120, 680), "FRONTIER MODELS  *  CLINICAL AI  *  SEMIS  *  POLICY", fill="#94a3b8", font=font_tag)

    # Cyan & Violet neural waveform bars
    bar_x = 120
    bar_y_base = 1180
    heights = [80, 150, 240, 340, 260, 390, 300, 420, 330, 220, 310, 370, 270, 170, 100]
    for idx, h in enumerate(heights):
        bar_color = "#06b6d4" if idx % 2 == 0 else "#a855f7"
        draw.rounded_rectangle([bar_x, bar_y_base - h, bar_x + 36, bar_y_base], radius=12, fill=bar_color)
        bar_x += 54

    draw.text((120, 1240), "Dr. Nikhil Shah  *  Daily Artificial Intelligence Briefing", fill="#64748b", font=font_tag)

    img.save(str(output_path), "JPEG", quality=95)
    return output_path


def generate_all_covers():
    """Generate 1400x1400 cover art images for all 3 podcast shows."""
    print("Generating podcast cover art images...")
    c1 = generate_edmonton_cover(Path("public/assets/cover.jpg"))
    generate_edmonton_cover(Path("public/assets/cover_edmonton.jpg"))
    c2 = generate_oilers_cover(Path("public/assets/cover_oilers.jpg"))
    c3 = generate_ai_cover(Path("public/assets/cover_ai.jpg"))
    print(f"  - Show 1 (Edmonton): {c1}")
    print(f"  - Show 2 (Oilers):   {c2}")
    print(f"  - Show 3 (AI):       {c3}")


if __name__ == "__main__":
    generate_all_covers()
