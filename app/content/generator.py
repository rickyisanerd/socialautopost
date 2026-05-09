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
