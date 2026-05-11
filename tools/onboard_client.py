"""
Client Onboarding Script
=========================
One-command onboarding for a new business client.

Creates the business in the database, adds platform credentials,
verifies everything works, and (optionally) fires a test post.

Usage:
    python tools/onboard_client.py

The script walks you through each step interactively.
For Meta tokens, run tools/meta_token_exchange.py first.
"""

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session, init_db
from app.models.models import Business, PlatformCredential, Post, PostDelivery
from app.platforms.facebook import FacebookClient
from app.platforms.instagram import InstagramClient
from app.platforms.x_twitter import XTwitterClient
from app.platforms.linkedin import LinkedInClient


def ask(prompt: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    while True:
        val = input(f"  {prompt}: ").strip()
        if val:
            return val
        print("    (required)")


def ask_optional(prompt: str) -> str:
    val = input(f"  {prompt} (optional, press Enter to skip): ").strip()
    return val


def ask_yn(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    val = input(f"  {prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


async def verify_facebook(page_id: str, token: str) -> bool:
    client = FacebookClient(page_id, token)
    try:
        ok = await client.verify_credentials()
        if ok:
            print("    Facebook: VERIFIED")
        else:
            print("    Facebook: FAILED — check page_id and token")
        return ok
    except Exception as e:
        print(f"    Facebook: ERROR — {e}")
        return False


async def verify_instagram(ig_id: str, token: str) -> bool:
    client = InstagramClient(ig_id, token)
    try:
        ok = await client.verify_credentials()
        if ok:
            print("    Instagram: VERIFIED")
        else:
            print("    Instagram: FAILED — check ig_account_id and token")
        return ok
    except Exception as e:
        print(f"    Instagram: ERROR — {e}")
        return False


async def verify_x(api_key: str, api_secret: str, access_token: str, access_secret: str) -> bool:
    client = XTwitterClient(api_key, api_secret, access_token, access_secret)
    try:
        ok = await client.verify_credentials()
        if ok:
            print("    X/Twitter: VERIFIED")
        else:
            print("    X/Twitter: FAILED — check API keys")
        return ok
    except Exception as e:
        print(f"    X/Twitter: ERROR — {e}")
        return False


async def verify_linkedin(access_token: str, org_id: str) -> bool:
    client = LinkedInClient(access_token, org_id)
    try:
        ok = await client.verify_credentials()
        if ok:
            print("    LinkedIn: VERIFIED")
        else:
            print("    LinkedIn: FAILED — check token and org_id")
        return ok
    except Exception as e:
        print(f"    LinkedIn: ERROR — {e}")
        return False


async def main():
    print("=" * 60)
    print("SOCIALAUTOPOST — NEW CLIENT ONBOARDING")
    print("=" * 60)

    # Initialize database
    await init_db()

    # ─── Business Info ───────────────────────────────────────
    print("\n--- BUSINESS INFORMATION ---\n")
    name = ask("Business name")
    description = ask("Short description (what they do, 1-2 sentences)")
    industry = ask("Industry (e.g., Automotive Repair, Restaurant, Real Estate)")
    location = ask("Address or city")
    phone = ask_optional("Phone number")
    website = ask_optional("Website URL")
    services = ask("Services offered (comma-separated)")
    target_audience = ask("Target audience", f"Customers in {location.split(',')[0] if ',' in location else location}")
    tone = ask("Brand voice/tone", "friendly and professional")
    color_primary = ask("Primary brand color (hex)", "#1a73e8")
    color_secondary = ask("Secondary brand color (hex)", "#ffffff")
    posting_days = ask("Posting days", "tuesday,friday")
    posting_time = ask("Posting time (24h)", "10:00")
    timezone = ask("Timezone", "America/Chicago")

    # ─── Create Business ─────────────────────────────────────
    print("\nCreating business...")
    async with async_session() as db:
        biz = Business(
            name=name, description=description, industry=industry,
            location=location, phone=phone, website_url=website,
            brand_color_primary=color_primary,
            brand_color_secondary=color_secondary,
            tone=tone, target_audience=target_audience, services=services,
            posting_days=posting_days, posting_time=posting_time,
            timezone=timezone,
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)
        biz_id = biz.id
        print(f"Business created: ID={biz_id}")

    # ─── Platform Credentials ────────────────────────────────
    print("\n--- PLATFORM CREDENTIALS ---")
    print("For each platform, enter credentials or press Enter to skip.\n")

    platforms_added = []

    # Facebook
    print("[Facebook]")
    fb_token = ask_optional("Page Access Token (run meta_token_exchange.py first)")
    if fb_token:
        fb_page_id = ask("Facebook Page ID")
        ok = await verify_facebook(fb_page_id, fb_token)
        if ok or ask_yn("Add anyway despite verification failure?", default=False):
            async with async_session() as db:
                cred = PlatformCredential(
                    business_id=biz_id, platform="facebook",
                    credentials={"page_id": fb_page_id, "access_token": fb_token},
                )
                db.add(cred)
                await db.commit()
            platforms_added.append("facebook")
            print("    Added Facebook.\n")
    else:
        print("    Skipped.\n")

    # Instagram
    print("[Instagram]")
    ig_token = ask_optional("Access Token (same as Facebook page token)")
    if ig_token:
        ig_id = ask("Instagram Business Account ID")
        ok = await verify_instagram(ig_id, ig_token)
        if ok or ask_yn("Add anyway despite verification failure?", default=False):
            async with async_session() as db:
                cred = PlatformCredential(
                    business_id=biz_id, platform="instagram",
                    credentials={"ig_account_id": ig_id, "access_token": ig_token},
                )
                db.add(cred)
                await db.commit()
            platforms_added.append("instagram")
            print("    Added Instagram.\n")
    else:
        print("    Skipped.\n")

    # X/Twitter
    print("[X / Twitter]")
    x_key = ask_optional("API Key")
    if x_key:
        x_secret = ask("API Secret")
        x_token = ask("Access Token")
        x_token_secret = ask("Access Token Secret")
        ok = await verify_x(x_key, x_secret, x_token, x_token_secret)
        if ok or ask_yn("Add anyway despite verification failure?", default=False):
            async with async_session() as db:
                cred = PlatformCredential(
                    business_id=biz_id, platform="x",
                    credentials={
                        "api_key": x_key, "api_secret": x_secret,
                        "access_token": x_token, "access_token_secret": x_token_secret,
                    },
                )
                db.add(cred)
                await db.commit()
            platforms_added.append("x")
            print("    Added X/Twitter.\n")
    else:
        print("    Skipped.\n")

    # LinkedIn
    print("[LinkedIn]")
    li_token = ask_optional("Access Token")
    if li_token:
        li_org = ask("Organization ID")
        ok = await verify_linkedin(li_token, li_org)
        if ok or ask_yn("Add anyway despite verification failure?", default=False):
            async with async_session() as db:
                cred = PlatformCredential(
                    business_id=biz_id, platform="linkedin",
                    credentials={"access_token": li_token, "org_id": li_org},
                )
                db.add(cred)
                await db.commit()
            platforms_added.append("linkedin")
            print("    Added LinkedIn.\n")
    else:
        print("    Skipped.\n")

    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ONBOARDING COMPLETE")
    print("=" * 60)
    print(f"Business:   {name} (ID: {biz_id})")
    print(f"Platforms:  {', '.join(platforms_added) if platforms_added else 'NONE'}")
    print(f"Schedule:   {posting_days} at {posting_time} {timezone}")
    print(f"Dashboard:  /dashboard/business/{biz_id}")

    if not platforms_added:
        print("\nWARNING: No platforms added. The scheduler will generate content but")
        print("have nowhere to post it. Add platforms via the dashboard or re-run this tool.")
        return

    # ─── Test Post ───────────────────────────────────────────
    if ask_yn("\nFire a test post now?"):
        print("Running post cycle...")
        from app.core.orchestrator import run_post_cycle
        try:
            await run_post_cycle(business_id=biz_id)
            print("Post cycle complete. Check the dashboard for results.")
        except Exception as e:
            print(f"Post cycle failed: {e}")
    else:
        print(f"\nTo test later: POST /api/businesses/{biz_id}/post-now")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(main())
