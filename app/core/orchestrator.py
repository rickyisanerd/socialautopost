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
from app.core.notifications import send_post_notification

log = logging.getLogger("socialautopost")


def _public_image_url(image_path: str) -> str:
    """Build a public URL for a generated image served by our app.

    Images are stored in generated/images/ and served at /static/images/.
    This gives Instagram a URL that doesn't depend on Facebook at all.
    """
    from pathlib import Path
    filename = Path(image_path).name
    base = settings.base_url.rstrip("/")
    return f"{base}/static/images/{filename}"


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


async def _get_recent_post_texts(db: AsyncSession, business_id: int, limit: int = 10) -> list[str]:
    """Fetch recent post texts so the AI can avoid repeating topics."""
    result = await db.execute(
        select(Post.content_text)
        .where(Post.business_id == business_id)
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    return [row[0] for row in result.fetchall()]


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
        "phone": biz.phone or "",
        "website": biz.website_url or "",
    }

    recent_posts = await _get_recent_post_texts(db, biz.id)
    content = await generate_post_content(biz_dict, settings.anthropic_api_key, recent_posts=recent_posts)

    image_path = generate_post_image(
        headline=content["headline"],
        tagline=content["image_tagline"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
        phone=biz.phone or "",
        website=biz.website_url or "",
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

    # Self-hosted image URL for Instagram — no Facebook dependency
    self_hosted_url = _public_image_url(image_path)
    log.info(f"Self-hosted image URL for Instagram: {self_hosted_url}")
    delivery_results = []

    for cred in creds:
        delivery = PostDelivery(post_id=post.id, platform=cred.platform, status="pending")
        db.add(delivery)
        await db.flush()

        client = _build_client(cred.platform, cred.credentials)
        if not client:
            delivery.status = "failed"
            delivery.error_message = f"Unknown platform: {cred.platform}"
            delivery_results.append({"platform": cred.platform, "status": "failed", "error": delivery.error_message})
            continue

        try:
            if cred.platform == "instagram":
                result = await client.post(content["text"], image_url=self_hosted_url)
            else:
                result = await client.post(content["text"], image_path=image_path)

            if result["success"]:
                delivery.status = "delivered"
                delivery.platform_post_id = result["post_id"]
                delivery.delivered_at = datetime.now(timezone.utc)
                log.info(f"Posted to {cred.platform} for {biz.name}: {result['post_id']}")
                delivery_results.append({"platform": cred.platform, "status": "delivered", "error": None})
            else:
                delivery.status = "failed"
                delivery.error_message = result["error"]
                log.error(f"Failed posting to {cred.platform} for {biz.name}: {result['error']}")
                delivery_results.append({"platform": cred.platform, "status": "failed", "error": result["error"]})
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            log.error(f"Exception posting to {cred.platform} for {biz.name}: {e}")
            delivery_results.append({"platform": cred.platform, "status": "failed", "error": str(e)})

    await db.commit()
    log.info(f"Completed image post cycle for {biz.name}")

    send_post_notification(
        business_name=biz.name,
        post_type=content["post_type"],
        content_text=content["text"],
        image_path=image_path,
        deliveries=delivery_results,
    )


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
        "phone": biz.phone or "",
        "website": biz.website_url or "",
    }

    recent_posts = await _get_recent_post_texts(db, biz.id)
    reel_content = await generate_reel_content(biz_dict, settings.anthropic_api_key, recent_posts=recent_posts)

    video_path = generate_reel(
        headline=reel_content["headline"],
        tagline=reel_content["tagline"],
        cta_text=reel_content["cta"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
        phone=biz.phone or "",
        website=biz.website_url or "",
    )

    # Also generate a static image for platforms that don't support video (X/Twitter)
    image_path = generate_post_image(
        headline=reel_content["headline"],
        tagline=reel_content["tagline"],
        business_name=biz.name,
        primary_color=biz.brand_color_primary,
        secondary_color=biz.brand_color_secondary,
        phone=biz.phone or "",
        website=biz.website_url or "",
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

    # Self-hosted image URL for Instagram — no Facebook dependency
    self_hosted_url = _public_image_url(image_path)
    log.info(f"Self-hosted image URL for Instagram: {self_hosted_url}")
    delivery_results = []

    for cred in creds:
        delivery = PostDelivery(post_id=post.id, platform=cred.platform, status="pending")
        db.add(delivery)
        await db.flush()

        client = _build_client(cred.platform, cred.credentials)
        if not client:
            delivery.status = "failed"
            delivery.error_message = f"Unknown platform: {cred.platform}"
            delivery_results.append({"platform": cred.platform, "status": "failed", "error": delivery.error_message})
            continue

        try:
            if cred.platform == "facebook":
                result = await client.post_reel(caption, video_path)
            elif cred.platform == "instagram":
                # Post the static ad image — self-hosted URL, no Facebook dependency
                result = await client.post(caption, image_url=self_hosted_url)
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
                delivery_results.append({"platform": cred.platform, "status": "delivered", "error": None})
            else:
                delivery.status = "failed"
                delivery.error_message = result["error"]
                log.error(f"Failed reel to {cred.platform} for {biz.name}: {result['error']}")
                delivery_results.append({"platform": cred.platform, "status": "failed", "error": result["error"]})
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            log.error(f"Exception posting reel to {cred.platform} for {biz.name}: {e}")
            delivery_results.append({"platform": cred.platform, "status": "failed", "error": str(e)})

    await db.commit()
    log.info(f"Completed reel cycle for {biz.name}")

    send_post_notification(
        business_name=biz.name,
        post_type="reel",
        content_text=caption,
        image_path=image_path,  # Send the static image preview, not the video
        deliveries=delivery_results,
    )
