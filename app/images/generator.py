from PIL import Image, ImageDraw, ImageFont
import os
import uuid
from pathlib import Path

OUTPUT_DIR = Path("generated/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 1080
HEIGHT = 1080


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_post_image(
    headline: str,
    tagline: str,
    business_name: str,
    primary_color: str = "#1a73e8",
    secondary_color: str = "#ffffff",
) -> str:
    primary_rgb = _hex_to_rgb(primary_color)
    secondary_rgb = _hex_to_rgb(secondary_color)

    img = Image.new("RGB", (WIDTH, HEIGHT), primary_rgb)
    draw = ImageDraw.Draw(img)

    # Decorative accent bar at top
    draw.rectangle([0, 0, WIDTH, 8], fill=secondary_rgb)

    # Bottom band for business name
    band_y = HEIGHT - 120
    band_color = tuple(max(0, c - 30) for c in primary_rgb)
    draw.rectangle([0, band_y, WIDTH, HEIGHT], fill=band_color)
    draw.rectangle([0, band_y, WIDTH, band_y + 3], fill=secondary_rgb)

    # Headline
    headline_font = _get_font(64)
    margin = 80
    max_text_width = WIDTH - margin * 2
    headline_lines = _wrap_text(draw, headline.upper(), headline_font, max_text_width)

    total_headline_height = len(headline_lines) * 80
    tagline_font = _get_font(32)
    tagline_lines = _wrap_text(draw, tagline, tagline_font, max_text_width)
    total_tagline_height = len(tagline_lines) * 45

    total_content_height = total_headline_height + 30 + total_tagline_height
    start_y = (band_y - total_content_height) // 2

    for i, line in enumerate(headline_lines):
        bbox = draw.textbbox((0, 0), line, font=headline_font)
        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2
        y = start_y + i * 80
        draw.text((x, y), line, fill=secondary_rgb, font=headline_font)

    tagline_start_y = start_y + total_headline_height + 30
    for i, line in enumerate(tagline_lines):
        bbox = draw.textbbox((0, 0), line, font=tagline_font)
        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2
        y = tagline_start_y + i * 45
        draw.text((x, y), line, fill=secondary_rgb, font=tagline_font)

    # Business name in bottom band
    name_font = _get_font(28)
    bbox = draw.textbbox((0, 0), business_name, font=name_font)
    name_width = bbox[2] - bbox[0]
    name_x = (WIDTH - name_width) // 2
    name_y = band_y + 45
    draw.text((name_x, name_y), business_name, fill=secondary_rgb, font=name_font)

    # Decorative corner accents
    accent_len = 60
    accent_width = 4
    for corner_x, corner_y, dx, dy in [
        (margin - 20, start_y - 40, 1, 1),
        (WIDTH - margin + 20, start_y - 40, -1, 1),
        (margin - 20, tagline_start_y + total_tagline_height + 20, 1, -1),
        (WIDTH - margin + 20, tagline_start_y + total_tagline_height + 20, -1, -1),
    ]:
        draw.rectangle(
            [corner_x, corner_y, corner_x + accent_len * dx, corner_y + accent_width * dy],
            fill=secondary_rgb,
        )
        draw.rectangle(
            [corner_x, corner_y, corner_x + accent_width * dx, corner_y + accent_len * dy],
            fill=secondary_rgb,
        )

    filename = f"{uuid.uuid4().hex[:12]}.png"
    filepath = OUTPUT_DIR / filename
    img.save(filepath, "PNG", quality=95)
    return str(filepath)
