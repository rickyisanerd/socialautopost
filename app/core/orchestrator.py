import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session
from app.core.config import settings
from app.content.generator import generate_post_content
from app.images.generator import generate_post_image
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


async def run_post_cycle(business_id: int | None = None):
    """Generate content + image, then post to all active platforms for each active business."""
    async with async_session() as db:
        query = select(Business).where(Business.is_active == True)
        if business_id:
            query = query.where(Business.id == business_id)
        result = await db.execute(query)
        businesses = result.scalars().all()

        for biz in businesses:
            try:
                await _process_business(db, biz)
            except Exception as e:
                log.error(f"Failed to process business {biz.name}: {e}")


async def _process_business(db: AsyncSession, biz: Business):
    log.info(f"Generating content for {biz.name}")

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
                # Instagram requires a public URL, not a local path
                image_filename = image_path.split("/")[-1]
                public_image_url = f"{settings.base_url}/static/images/{image_filename}"
                result = await client.post(content["text"], image_url=public_image_url)
            else:
                result = await client.post(content["text"], image_path=image_path)

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
    log.info(f"Completed post cycle for {biz.name}")
