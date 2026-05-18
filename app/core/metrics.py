"""Periodic metrics collection for all delivered posts."""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.models.models import Business, PlatformCredential, Post, PostDelivery, PostMetrics

log = logging.getLogger("socialautopost")


def _build_client(platform: str, creds: dict):
    """Build a platform client for metrics fetching."""
    from app.platforms.facebook import FacebookClient
    from app.platforms.instagram import InstagramClient
    from app.platforms.x_twitter import XTwitterClient
    from app.platforms.linkedin import LinkedInClient

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


async def collect_metrics():
    """Fetch engagement metrics for all delivered posts from the last 30 days."""
    log.info("Starting metrics collection cycle")
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async with async_session() as db:
        # Get all businesses with their credentials
        biz_result = await db.execute(
            select(Business).options(selectinload(Business.platforms))
        )
        businesses = biz_result.scalars().all()

        # Build a lookup: business_id -> {platform: client}
        clients = {}
        for biz in businesses:
            clients[biz.id] = {}
            for cred in biz.platforms:
                if cred.is_active:
                    client = _build_client(cred.platform, cred.credentials)
                    if client:
                        clients[biz.id][cred.platform] = client

        # Get all delivered posts from the last 30 days
        result = await db.execute(
            select(PostDelivery)
            .join(Post)
            .where(
                PostDelivery.status == "delivered",
                PostDelivery.platform_post_id != "",
                Post.created_at >= cutoff,
            )
            .options(selectinload(PostDelivery.post), selectinload(PostDelivery.metrics))
        )
        deliveries = result.scalars().all()

        updated = 0
        failed = 0

        for delivery in deliveries:
            biz_clients = clients.get(delivery.post.business_id, {})
            client = biz_clients.get(delivery.platform)
            if not client:
                continue

            metrics_data = await client.get_metrics(delivery.platform_post_id)
            if not metrics_data:
                failed += 1
                continue

            # Update or create metrics record
            if delivery.metrics:
                m = delivery.metrics
            else:
                m = PostMetrics(delivery_id=delivery.id)
                db.add(m)

            m.impressions = metrics_data.get("impressions", 0)
            m.reach = metrics_data.get("reach", 0)
            m.likes = metrics_data.get("likes", 0)
            m.comments = metrics_data.get("comments", 0)
            m.shares = metrics_data.get("shares", 0)
            m.saves = metrics_data.get("saves", 0)
            m.clicks = metrics_data.get("clicks", 0)
            m.engagement = metrics_data.get("engagement", 0)
            m.updated_at = datetime.now(timezone.utc)
            updated += 1

        await db.commit()
        log.info(f"Metrics collection complete: {updated} updated, {failed} failed out of {len(deliveries)} deliveries")
