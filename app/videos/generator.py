"""
Video Reel Generator
=====================
Creates short (10-15 second) animated video reels from branded images.
Uses moviepy to add Ken Burns (zoom/pan) effects, text reveals, and transitions.
No paid APIs — purely local generation.

Output: 1080x1920 vertical MP4 (9:16 for Reels/Shorts)
"""
import os
import uuid
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import numpy as np
from moviepy import (
    ImageClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
    vfx,
)

log = logging.getLogger("socialautopost")

OUTPUT_DIR = Path("generated/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Reel dimensions (vertical 9:16)
REEL_W = 1080
REEL_H = 1920
FPS = 30
TOTAL_DURATION = 12  # seconds


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _get_font_path(bold: bool = True) -> str:
    if bold:
        paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        paths = [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _create_branded_frame(
    text: str,
    business_name: str,
    primary_color: str,
    secondary_color: str,
    font_size: int = 72,
) -> np.ndarray:
    """Create a single branded frame as a numpy array (for moviepy)."""
    primary_rgb = _hex_to_rgb(primary_color)
    secondary_rgb = _hex_to_rgb(secondary_color)

    img = Image.new("RGB", (REEL_W, REEL_H), primary_rgb)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([0, 0, REEL_W, 8], fill=secondary_rgb)

    # Bottom band for business name
    band_y = REEL_H - 200
    band_color = tuple(max(0, c - 30) for c in primary_rgb)
    draw.rectangle([0, band_y, REEL_W, REEL_H], fill=band_color)
    draw.rectangle([0, band_y, REEL_W, band_y + 3], fill=secondary_rgb)

    # Main text
    font_path = _get_font_path(bold=True)
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Word wrap
    margin = 80
    max_width = REEL_W - margin * 2
    words = text.upper().split()
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

    line_height = font_size + 16
    total_text_height = len(lines) * line_height
    start_y = (band_y - total_text_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (REEL_W - text_w) // 2
        y = start_y + i * line_height
        draw.text((x, y), line, fill=secondary_rgb, font=font)

    # Corner accents
    accent_len = 60
    accent_w = 4
    for cx, cy, dx, dy in [
        (margin - 20, start_y - 40, 1, 1),
        (REEL_W - margin + 20, start_y - 40, -1, 1),
        (margin - 20, start_y + total_text_height + 20, 1, -1),
        (REEL_W - margin + 20, start_y + total_text_height + 20, -1, -1),
    ]:
        x1, x2 = cx, cx + accent_len * dx
        y1, y2 = cy, cy + accent_w * dy
        draw.rectangle([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)], fill=secondary_rgb)
        x1, x2 = cx, cx + accent_w * dx
        y1, y2 = cy, cy + accent_len * dy
        draw.rectangle([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)], fill=secondary_rgb)

    # Business name in bottom band
    if font_path:
        name_font = ImageFont.truetype(font_path, 36)
    else:
        name_font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), business_name, font=name_font)
    name_w = bbox[2] - bbox[0]
    draw.text(((REEL_W - name_w) // 2, band_y + 80), business_name, fill=secondary_rgb, font=name_font)

    return np.array(img)


def _zoom_in_effect(clip, zoom_ratio=0.08):
    """Slow zoom in (Ken Burns) effect."""
    def effect(get_frame, t):
        img = get_frame(t)
        h, w = img.shape[:2]
        # Calculate zoom for this frame
        zoom = 1 + (zoom_ratio * t / clip.duration)
        # New dimensions
        new_h, new_w = int(h * zoom), int(w * zoom)
        # Resize
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(img)
        pil_img = pil_img.resize((new_w, new_h), PILImage.LANCZOS)
        # Crop center
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        pil_img = pil_img.crop((left, top, left + w, top + h))
        return np.array(pil_img)
    return clip.transform(effect)


def generate_reel(
    headline: str,
    tagline: str,
    cta_text: str,
    business_name: str,
    primary_color: str = "#1a73e8",
    secondary_color: str = "#ffffff",
) -> str:
    """
    Generate a short video reel with 3 scenes:
    1. Headline with zoom-in effect (4s)
    2. Tagline/value prop (4s)
    3. Call to action (4s)

    Returns path to the generated MP4 file.
    """
    log.info(f"Generating video reel for {business_name}")

    # Scene 1: Headline
    frame1 = _create_branded_frame(headline, business_name, primary_color, secondary_color, font_size=80)
    scene1 = ImageClip(frame1, duration=4.0)
    scene1 = _zoom_in_effect(scene1, zoom_ratio=0.06)

    # Scene 2: Tagline
    frame2 = _create_branded_frame(tagline, business_name, primary_color, secondary_color, font_size=64)
    scene2 = ImageClip(frame2, duration=4.0)
    scene2 = _zoom_in_effect(scene2, zoom_ratio=0.06)

    # Scene 3: CTA
    frame3 = _create_branded_frame(cta_text, business_name, primary_color, secondary_color, font_size=72)
    scene3 = ImageClip(frame3, duration=4.0)
    scene3 = _zoom_in_effect(scene3, zoom_ratio=0.06)

    # Add fade transitions between scenes
    scene1 = scene1.with_effects([vfx.CrossFadeOut(0.5)])
    scene2 = scene2.with_effects([vfx.CrossFadeIn(0.5), vfx.CrossFadeOut(0.5)])
    scene3 = scene3.with_effects([vfx.CrossFadeIn(0.5)])

    # Composite all scenes
    final = concatenate_videoclips(
        [scene1, scene2, scene3],
        method="compose",
    )

    # Write output
    filename = f"reel_{uuid.uuid4().hex[:12]}.mp4"
    filepath = str(OUTPUT_DIR / filename)

    final.write_videofile(
        filepath,
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=4,
        logger=None,
    )

    log.info(f"Video reel generated: {filepath}")
    return filepath


if __name__ == "__main__":
    # Quick test
    path = generate_reel(
        headline="Expert Auto Repair You Can Trust",
        tagline="Brakes, Engine, Transmission — Done Right The First Time",
        cta_text="Call Today For A Free Estimate",
        business_name="New Beginning Autos Care",
        primary_color="#1a2744",
        secondary_color="#d4af37",
    )
    print(f"Generated: {path}")
