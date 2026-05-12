import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session
from app.core.config import settings
from app.content.generator import generate_post_content, generate_reel_content
from app.images.generator import generate_post_image
from app.videos.generator import generate_reel
from app.models.models import Business, PlatformCredential, Post, PostDelivery
from app.platforms.facebook import FacebookClient
from app.platforms.instagram import InstagramClient
from app.platforms.x_twitter import XTwitterClient
from app.platforms.linkedin import LinkedInClient

log = logging.getLogger("socialautopost")


def _build_client(platform: str, creds: dict):
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


async def run_post_cycle(business_id: int | None = None, force_reel: bool = False):
    """Generate content + image/video, then post to all active platforms."""
    async with async_session() as db:
        query = select(Business).where(Business.is_active == True)
        if business_id:
            query = query.where(Business.id == business_id)
        result = await db.execute(query)
        businesses = result.scalars().all()

        for biz in businesses:
            try:
                # Decide if this cycle should be a reel or image post
                # Alternate: every other post is a reel
                post_count = await db.execute(
                    select(func.count()).select_from(Post).where(Post.business_id == biz.id)
                )
                total_posts = post_count.scalar() or 0
                is_reel = force_reel or (total_posts % 2 == 1)  # Odd posts = reel

                if is_reel:
                    await _process_reel(db, biz)
                else:
                    await _process_business(db, biz)
            except Exception as e:
                log.error(f"Failed to process business {biz.name}: {e}")


async def _process_business(db: AsyncSession, biz: Business):
    """Standard image post flow."""
    log.info(f"Generating image post for {biz.name}")

    biz_dict = {
        "name": biz.name,
        "description": biz.description,
        "industry": biz.industry,
        "location": biz.location,
        "services": biz.services,
        "target_audience": biz.target_audience,
        "tone": biz.tone,
    }

    content = await generate_post_content(biz_dict, settings.anthropic_api_key)

    image_path = generate_post_image(
        headline=content["headline"],
        tagline=content["image_tagline"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
    )

    post = Post(
        business_id=biz.id,
        content_text=content["text"],
        image_path=image_path,
        post_type=content["post_type"],
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(post)
    await db.flush()

    cred_result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.business_id == biz.id,
            PlatformCredential.is_active == True,
        )
    )
    creds = cred_result.scalars().all()

    # Sort so Facebook posts first — we grab its CDN URL for Instagram
    creds = sorted(creds, key=lambda c: 0 if c.platform == "facebook" else (2 if c.platform == "instagram" else 1))
    fb_image_url = None

    for cred in creds:
        delivery = PostDelivery(post_id=post.id, platform=cred.platform, status="pending")
        db.add(delivery)
        await db.flush()

        client = _build_client(cred.platform, cred.credentials)
        if not client:
            delivery.status = "failed"
            delivery.error_message = f"Unknown platform: {cred.platform}"
            continue

        try:
            if cred.platform == "instagram":
                if fb_image_url:
                    result = await client.post(content["text"], image_url=fb_image_url)
                else:
                    result = {"success": False, "post_id": "",
                              "error": "No public image URL — Facebook must post first"}
            else:
                result = await client.post(content["text"], image_path=image_path)

            if cred.platform == "facebook" and result.get("success") and result.get("image_url"):
                fb_image_url = result["image_url"]
                log.info(f"Got Facebook CDN URL for Instagram: {fb_image_url[:80]}...")

            if result["success"]:
                delivery.status = "delivered"
                delivery.platform_post_id = result["post_id"]
                delivery.delivered_at = datetime.now(timezone.utc)
                log.info(f"Posted to {cred.platform} for {biz.name}: {result['post_id']}")
            else:
                delivery.status = "failed"
                delivery.error_message = result["error"]
                log.error(f"Failed posting to {cred.platform} for {biz.name}: {result['error']}")
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            log.error(f"Exception posting to {cred.platform} for {biz.name}: {e}")

    await db.commit()
    log.info(f"Completed image post cycle for {biz.name}")


async def _process_reel(db: AsyncSession, biz: Business):
    """Video reel flow — generate video, post as Reel to Facebook/Instagram, image to X."""
    log.info(f"Generating video reel for {biz.name}")

    biz_dict = {
        "name": biz.name,
        "description": biz.description,
        "industry": biz.industry,
        "location": biz.location,
        "services": biz.services,
        "target_audience": biz.target_audience,
        "tone": biz.tone,
    }

    reel_content = await generate_reel_content(biz_dict, settings.anthropic_api_key)

    video_path = generate_reel(
        headline=reel_content["headline"],
        tagline=reel_content["tagline"],
        cta_text=reel_content["cta"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
    )

    # Also generate a static image for platforms that don't support video (X/Twitter)
    image_path = generate_post_image(
        headline=reel_content["headline"],
        tagline=reel_content["tagline"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
    )

    caption = reel_content.get("caption", reel_content["headline"])

    post = Post(
        business_id=biz.id,
        content_text=caption,
        image_path=video_path,
        post_type="reel",
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(post)
    await db.flush()

    cred_result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.business_id == biz.id,
            PlatformCredential.is_active == True,
        )
    )
    creds = cred_result.scalars().all()

    # Facebook first — we need the video URL from FB for Instagram Reels
    creds = sorted(creds, key=lambda c: 0 if c.platform == "facebook" else (2 if c.platform == "instagram" else 1))
    fb_video_url = None

    for cred in creds:
        delivery = PostDelivery(post_id=post.id, platform=cred.platform, status="pending")
        db.add(delivery)
        await db.flush()

        client = _build_client(cred.platform, cred.credentials)
        if not client:
            delivery.status = "failed"
            delivery.error_message = f"Unknown platform: {cred.platform}"
            continue

        try:
            if cred.platform == "facebook":
                result = await client.post_reel(caption, video_path)
                if result.get("success") and result.get("video_url"):
                    fb_video_url = result["video_url"]
                    log.info(f"Facebook Reel posted, URL: {fb_video_url}")
            elif cred.platform == "instagram":
                if fb_video_url:
                    result = await client.post_reel(caption, fb_video_url)
                else:
                    # Fall back to image post if no video URL available
                    log.warning("No FB video URL for Instagram reel, falling back to image post")
                    # Try to get an image URL via a quick FB image upload
                    fb_cred = next((c for c in creds if c.platform == "facebook"), None)
                    if fb_cred:
                        fb_client = _build_client("facebook", fb_cred.credentials)
                        img_result = await fb_client.post(caption, image_path=image_path)
                        if img_result.get("image_url"):
                            result = await client.post(caption, image_url=img_result["image_url"])
                        else:
                            result = {"success": False, "post_id": "", "error": "No public URL for Instagram"}
                    else:
                        result = {"success": False, "post_id": "", "error": "No FB credentials for image hosting"}
            elif cred.platform == "x":
                # X/Twitter doesn't support reels — post static image instead
                result = await client.post(caption, image_path=image_path)
            else:
                result = await client.post(caption, image_path=image_path)

            if result["success"]:
                delivery.status = "delivered"
                delivery.platform_post_id = result["post_id"]
                delivery.delivered_at = datetime.now(timezone.utc)
                log.info(f"Posted reel to {cred.platform} for {biz.name}: {result['post_id']}")
            else:
                delivery.status = "failed"
                delivery.error_message = result["error"]
                log.error(f"Failed reel to {cred.platform} for {biz.name}: {result['error']}")
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            log.error(f"Exception posting reel to {cred.platform} for {biz.name}: {e}")

    await db.commit()
    log.info(f"Completed reel cycle for {biz.name}")
