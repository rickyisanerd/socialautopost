import anthropic
import json
import random
from datetime import datetime


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

SYSTEM_PROMPT = """You are a social media marketing expert. You create short, engaging social media posts for small businesses.

Rules:
- Keep posts under 280 characters for broad compatibility
- Use 2-3 relevant hashtags maximum
- Include a clear call to action
- Match the business's tone and audience
- Never use generic filler — every word must earn its place
- Vary post style: questions, tips, offers, stories, facts
- Do NOT use emojis excessively — 0 to 2 max per post

Return ONLY valid JSON with these fields:
{
  "text": "the post text with hashtags",
  "headline": "short 3-6 word headline for the image",
  "image_tagline": "one short phrase for the image subtext"
}"""


def _build_prompt(business: dict, post_type: str) -> str:
    return f"""Create a {post_type} social media post for this business:

Business: {business['name']}
Industry: {business['industry']}
Description: {business['description']}
Services: {business.get('services', 'N/A')}
Location: {business.get('location', 'N/A')}
Target Audience: {business.get('target_audience', 'local customers')}
Tone: {business.get('tone', 'professional')}
Today's Date: {datetime.now().strftime('%B %d, %Y')}

Post type: {post_type}
Make it specific to this business — no generic marketing fluff."""


async def generate_post_content(business: dict, api_key: str, post_type: str | None = None) -> dict:
    if not post_type:
        post_type = random.choice(POST_TYPES)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(business, post_type)}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    result["post_type"] = post_type
    return result


REEL_SYSTEM_PROMPT = """You are a social media video content expert. You create punchy, short-form video scripts for small business Reels/Shorts.

The video has 3 scenes (4 seconds each, 12 seconds total). Each scene shows bold text on a branded background.

Rules:
- Scene 1 (headline): Attention-grabbing hook, 3-7 words, make them stop scrolling
- Scene 2 (tagline): Value proposition or key selling point, 5-12 words
- Scene 3 (cta): Clear call to action, 4-8 words
- Also provide a caption for the reel post (under 200 chars, 2-3 hashtags)
- Match the business's tone and audience
- Be specific to the business, not generic

Return ONLY valid JSON:
{
  "headline": "short punchy hook",
  "tagline": "value proposition line",
  "cta": "call to action",
  "caption": "reel caption text with #hashtags"
}"""


async def generate_reel_content(business: dict, api_key: str) -> dict:
    post_type = random.choice(["promotional", "educational", "special_offer", "tip_of_the_week"])

    prompt = f"""Create a short video reel script for this business:

Business: {business['name']}
Industry: {business['industry']}
Description: {business['description']}
Services: {business.get('services', 'N/A')}
Location: {business.get('location', 'N/A')}
Target Audience: {business.get('target_audience', 'local customers')}
Tone: {business.get('tone', 'professional')}
Today's Date: {datetime.now().strftime('%B %d, %Y')}

Style: {post_type}
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
