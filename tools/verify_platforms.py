"""
Platform Credential Health Check
=================================
Verifies all platform credentials across all businesses are still valid.
Run this periodically or before a manual post cycle to catch expired tokens.

Usage:
    python tools/verify_platforms.py
    python tools/verify_platforms.py --business-id 1
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session, init_db
from app.models.models import Business, PlatformCredential
from app.platforms.facebook import FacebookClient
from app.platforms.instagram import InstagramClient
from app.platforms.x_twitter import XTwitterClient
from app.platforms.linkedin import LinkedInClient


def build_client(platform: str, creds: dict):
    match platform:
        case "facebook":
            return FacebookClient(creds["page_id"], creds["access_token"])
        case "instagram":
            return InstagramClient(creds["ig_account_id"], creds["access_token"])
        case "x":
            return XTwitterClient(
                creds["api_key"], creds["api_secret"],
                creds["access_token"], creds["access_token_secret"],
            )
        case "linkedin":
            return LinkedInClient(creds["access_token"], creds["org_id"])
    return None


async def main():
    parser = argparse.ArgumentParser(description="Verify platform credentials")
    parser.add_argument("--business-id", type=int, help="Check a specific business only")
    args = parser.parse_args()

    await init_db()

    print("=" * 60)
    print("PLATFORM CREDENTIAL HEALTH CHECK")
    print("=" * 60)

    async with async_session() as db:
        biz_query = select(Business).where(Business.is_active == True)
        if args.business_id:
            biz_query = biz_query.where(Business.id == args.business_id)
        businesses = (await db.execute(biz_query)).scalars().all()

        if not businesses:
            print("No active businesses found.")
            return

        total = 0
        passed = 0
        failed = 0

        for biz in businesses:
            print(f"\n{biz.name} (ID: {biz.id})")
            print("-" * 40)

            creds = (await db.execute(
                select(PlatformCredential).where(
                    PlatformCredential.business_id == biz.id,
                    PlatformCredential.is_active == True,
                )
            )).scalars().all()

            if not creds:
                print("  No platforms configured.")
                continue

            for cred in creds:
                total += 1
                client = build_client(cred.platform, cred.credentials)
                if not client:
                    print(f"  {cred.platform:12s}  UNKNOWN PLATFORM")
                    failed += 1
                    continue

                try:
                    ok = await client.verify_credentials()
                    if ok:
                        print(f"  {cred.platform:12s}  OK")
                        passed += 1
                    else:
                        print(f"  {cred.platform:12s}  FAILED — credentials rejected")
                        failed += 1
                except Exception as e:
                    print(f"  {cred.platform:12s}  ERROR — {e}")
                    failed += 1

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    if failed:
        print("Action needed: re-run meta_token_exchange.py or update credentials via dashboard.")
    print("=" * 60)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(main())
