"""
Quick test post — adds platform credentials to existing business and fires a test post.
Non-interactive, pulls creds from .env
"""
import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from app.core.database import async_session, init_db
from app.models.models import Business, PlatformCredential
from app.core.orchestrator import run_post_cycle
from sqlalchemy import select


async def main():
    await init_db()

    async with async_session() as db:
        # Get business ID 1 (New Beginning Autos Care)
        result = await db.execute(select(Business).where(Business.id == 1))
        biz = result.scalar_one_or_none()
        if not biz:
            print("ERROR: Business ID 1 not found!")
            return

        print(f"Business: {biz.name} (ID: {biz.id})")

        # Check existing credentials
        cred_result = await db.execute(
            select(PlatformCredential).where(PlatformCredential.business_id == 1)
        )
        existing = cred_result.scalars().all()

        if existing:
            print(f"Already has {len(existing)} platform(s): {[c.platform for c in existing]}")
        else:
            print("No platforms configured. Adding from .env...")

            # Facebook
            meta_token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
            meta_page_id = os.getenv("META_PAGE_ID", "")
            if meta_token and meta_page_id:
                db.add(PlatformCredential(
                    business_id=1, platform="facebook",
                    credentials={"page_id": meta_page_id, "access_token": meta_token},
                ))
                print("  + Facebook added")

            # Instagram
            ig_id = os.getenv("META_INSTAGRAM_ACCOUNT_ID", "")
            if meta_token and ig_id:
                db.add(PlatformCredential(
                    business_id=1, platform="instagram",
                    credentials={"ig_account_id": ig_id, "access_token": meta_token},
                ))
                print("  + Instagram added")

            # X/Twitter
            x_key = os.getenv("X_API_KEY", "")
            x_secret = os.getenv("X_API_SECRET", "")
            x_token = os.getenv("X_ACCESS_TOKEN", "")
            x_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET", "")
            if all([x_key, x_secret, x_token, x_token_secret]):
                db.add(PlatformCredential(
                    business_id=1, platform="x",
                    credentials={
                        "api_key": x_key, "api_secret": x_secret,
                        "access_token": x_token, "access_token_secret": x_token_secret,
                    },
                ))
                print("  + X/Twitter added")

            # LinkedIn (skip if empty)
            li_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
            li_org = os.getenv("LINKEDIN_ORG_ID", "")
            if li_token and li_org:
                db.add(PlatformCredential(
                    business_id=1, platform="linkedin",
                    credentials={"access_token": li_token, "org_id": li_org},
                ))
                print("  + LinkedIn added")
            else:
                print("  - LinkedIn skipped (no credentials)")

            await db.commit()
            print("Credentials saved.\n")

    # Fire test post
    print("=" * 60)
    print("FIRING TEST POST CYCLE")
    print("=" * 60)
    await run_post_cycle(business_id=1)
    print("\nDone! Check the dashboard or platform accounts for results.")


if __name__ == "__main__":
    asyncio.run(main())
