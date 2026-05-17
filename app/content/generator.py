import anthropic
import json
import random
from datetime import datetime
from app.content.holidays import get_upcoming_holiday


POST_TYPES = [
    "promotional",
    "educational",
    "testimonial_request",
    "seasonal",
    "behind_the_scenes",
    "tip_of_the_week",
    "special_offer",
    "community",
]

SYSTEM_PROMPT = """You are a social media marketing expert with a knack for humor. You create short, engaging, sometimes funny social media posts for small businesses.

Rules:
- Keep posts under 280 characters for broad compatibility
- Use 2-3 relevant hashtags maximum
- Include a clear call to action
- Match the business's tone and audience
- Never use generic filler — every word must earn its place
- Vary post style: questions, tips, offers, stories, facts, funny observations, relatable problems
- Do NOT use emojis excessively — 0 to 2 max per post
- Be funny when it fits — humor makes people stop scrolling. Use wit, relatable car/home/life moments, playful jabs at common frustrations. Don't force it, but don't be boring either.
- CRITICAL: You MUST write about a DIFFERENT topic than the recent posts listed. If recent posts covered AC repair, write about something else entirely — oil changes, brakes, transmissions, batteries, check engine lights, overheating, weird noises, etc. NEVER repeat a topic that appears in recent posts.

Return ONLY valid JSON with these fields:
{
  "text": "the post text with hashtags",
  "headline": "short 3-6 word headline for the image",
  "image_tagline": "one short phrase for the image subtext"
}"""


def _holiday_context() -> str:
    """Return holiday prompt injection if a holiday is within 7 days."""
    holiday = get_upcoming_holiday(days_ahead=7)
    if not holiday:
        return ""
    days_until = (holiday["date"] - datetime.now().date()).days
    timing = "TODAY" if days_until == 0 else f"in {days_until} day{'s' if days_until != 1 else ''}"
    return f"""
HOLIDAY ALERT: {holiday['name']} is {timing}!
Theme: {holiday['theme']}
Promo angle: {holiday['promo_angle']}
>>> Tie this post to the holiday. Work in a seasonal special, holiday greeting, or themed offer that makes sense for this business. <<<
"""


def _build_recent_posts_context(recent_posts: list[str]) -> str:
    """Format recent post texts so the AI knows what topics to avoid."""
    if not recent_posts:
        return ""
    posts_list = "\n".join(f"  - {p[:150]}" for p in recent_posts[:10])
    return f"""
RECENT POSTS (DO NOT repeat these topics — pick something completely different):
{posts_list}

>>> You MUST cover a different service, problem, or angle than anything above. <<<
"""


def _build_prompt(business: dict, post_type: str, recent_posts: list[str] | None = None) -> str:
    holiday = _holiday_context()
    recent = _build_recent_posts_context(recent_posts or [])
    return f"""Create a {post_type} social media post for this business:

Business: {business['name']}
Industry: {business['industry']}
Description: {business['description']}
Services: {business.get('services', 'N/A')}
Location: {business.get('location', 'N/A')}
Target Audience: {business.get('target_audience', 'local customers')}
Tone: {business.get('tone', 'professional')}
Phone: {business.get('phone', '')}
Website: {business.get('website', '')}
Today's Date: {datetime.now().strftime('%B %d, %Y')}
{holiday}{recent}
Post type: {post_type}
If a phone number or website is provided, naturally work it into the call to action.
Make it specific to this business — no generic marketing fluff."""


async def generate_post_content(business: dict, api_key: str, post_type: str | None = None, recent_posts: list[str] | None = None) -> dict:
    if not post_type:
        post_type = random.choice(POST_TYPES)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(business, post_type, recent_posts)}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    result["post_type"] = post_type
    return result


REEL_SYSTEM_PROMPT = """You are a social media video content expert with a sense of humor. You create punchy, short-form video scripts for small business Reels/Shorts.

The video has 3 scenes (4 seconds each, 12 seconds total). Each scene shows bold text on a branded background.

Rules:
- Scene 1 (headline): Attention-grabbing hook, 3-7 words, make them stop scrolling
- Scene 2 (tagline): Value proposition or key selling point, 5-12 words
- Scene 3 (cta): Clear call to action, 4-8 words
- Also provide a caption for the reel post (under 200 chars, 2-3 hashtags)
- Match the business's tone and audience
- Be specific to the business, not generic
- Be funny when appropriate — relatable problems, witty hooks, playful tone. Humor gets shares.
- CRITICAL: You MUST write about a DIFFERENT topic than the recent posts listed. NEVER repeat a topic from recent posts.

Return ONLY valid JSON:
{
  "headline": "short punchy hook",
  "tagline": "value proposition line",
  "cta": "call to action",
  "caption": "reel caption text with #hashtags"
}"""


async def generate_reel_content(business: dict, api_key: str, recent_posts: list[str] | None = None) -> dict:
    post_type = random.choice(["promotional", "educational", "special_offer", "tip_of_the_week"])

    holiday = _holiday_context()
    recent = _build_recent_posts_context(recent_posts or [])
    prompt = f"""Create a short video reel script for this business:

Business: {business['name']}
Industry: {business['industry']}
Description: {business['description']}
Services: {business.get('services', 'N/A')}
Location: {business.get('location', 'N/A')}
Target Audience: {business.get('target_audience', 'local customers')}
Tone: {business.get('tone', 'professional')}
Phone: {business.get('phone', '')}
Website: {business.get('website', '')}
Today's Date: {datetime.now().strftime('%B %d, %Y')}
{holiday}{recent}
Style: {post_type}
If a phone number or website is provided, work the phone number into the CTA scene text.
Make it specific — no generic marketing fluff."""

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=REEL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)
