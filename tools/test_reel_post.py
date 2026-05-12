"""Quick test — generate and post a video reel for New Beginning Autos Care."""
import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from app.core.database import async_session, init_db
from app.core.orchestrator import run_post_cycle


async def main():
    await init_db()
    print("=" * 60)
    print("TESTING VIDEO REEL POST CYCLE")
    print("=" * 60)
    await run_post_cycle(business_id=1, force_reel=True)
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
