"""Daily metrics report emails — one per business, sent to rickysautomations@gmail.com."""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.models.models import Business, Post, PostDelivery, PostMetrics
import httpx
from app.core.config import settings

log = logging.getLogger("socialautopost")

RESEND_API_URL = "https://api.resend.com/emails"
# Uses notification_email from settings (defaults to NOTIFICATION_EMAIL env var)
# To send to rickysautomations@gmail.com, verify a custom domain on Resend first


def _fmt(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def _delta_badge(current: int, previous: int) -> str:
    """Return an HTML snippet showing the change from previous period."""
    diff = current - previous
    if previous == 0 and current == 0:
        return ""
    if previous == 0:
        return '<span style="color:#2ea043;font-size:11px;"> ▲ new</span>'
    pct = round((diff / previous) * 100)
    if diff > 0:
        return f'<span style="color:#2ea043;font-size:11px;"> ▲ {pct}%</span>'
    elif diff < 0:
        return f'<span style="color:#da3633;font-size:11px;"> ▼ {abs(pct)}%</span>'
    return '<span style="color:#8b949e;font-size:11px;"> — 0%</span>'


async def _get_period_metrics(db, business_id: int, start: datetime, end: datetime) -> dict:
    """Aggregate metrics for a business across a date range."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(PostMetrics.impressions), 0),
            func.coalesce(func.sum(PostMetrics.reach), 0),
            func.coalesce(func.sum(PostMetrics.likes), 0),
            func.coalesce(func.sum(PostMetrics.comments), 0),
            func.coalesce(func.sum(PostMetrics.shares), 0),
            func.coalesce(func.sum(PostMetrics.saves), 0),
            func.coalesce(func.sum(PostMetrics.clicks), 0),
            func.coalesce(func.sum(PostMetrics.engagement), 0),
        )
        .join(PostDelivery, PostMetrics.delivery_id == PostDelivery.id)
        .join(Post, PostDelivery.post_id == Post.id)
        .where(
            Post.business_id == business_id,
            Post.created_at >= start,
            Post.created_at < end,
        )
    )
    row = result.one()
    return {
        "impressions": row[0],
        "reach": row[1],
        "likes": row[2],
        "comments": row[3],
        "shares": row[4],
        "saves": row[5],
        "clicks": row[6],
        "engagement": row[7],
    }


async def _get_platform_breakdown(db, business_id: int, start: datetime, end: datetime) -> dict:
    """Get per-platform metric totals."""
    result = await db.execute(
        select(
            PostDelivery.platform,
            func.coalesce(func.sum(PostMetrics.impressions), 0),
            func.coalesce(func.sum(PostMetrics.likes), 0),
            func.coalesce(func.sum(PostMetrics.comments), 0),
            func.coalesce(func.sum(PostMetrics.shares), 0),
            func.coalesce(func.sum(PostMetrics.engagement), 0),
            func.count(PostDelivery.id),
        )
        .join(PostDelivery, PostMetrics.delivery_id == PostDelivery.id)
        .join(Post, PostDelivery.post_id == Post.id)
        .where(
            Post.business_id == business_id,
            Post.created_at >= start,
            Post.created_at < end,
        )
        .group_by(PostDelivery.platform)
    )
    platforms = {}
    for row in result.fetchall():
        platforms[row[0]] = {
            "impressions": row[1],
            "likes": row[2],
            "comments": row[3],
            "shares": row[4],
            "engagement": row[5],
            "post_count": row[6],
        }
    return platforms


async def _get_recent_posts(db, business_id: int, start: datetime, end: datetime) -> list:
    """Get posts from the period with their delivery statuses and metrics."""
    result = await db.execute(
        select(Post)
        .where(
            Post.business_id == business_id,
            Post.created_at >= start,
            Post.created_at < end,
        )
        .options(
            selectinload(Post.deliveries).selectinload(PostDelivery.metrics)
        )
        .order_by(Post.created_at.desc())
    )
    return result.scalars().all()


def _build_metric_card(label: str, value: int, delta_html: str = "") -> str:
    return f"""
    <td style="padding:12px;text-align:center;background:#161b22;border:1px solid #30363d;border-radius:8px;">
      <div style="font-size:22px;font-weight:bold;color:#58a6ff;">{_fmt(value)}</div>
      <div style="font-size:11px;color:#8b949e;margin-top:2px;">{label}{delta_html}</div>
    </td>"""


def _platform_color(platform: str) -> str:
    return {
        "facebook": "#1877f2",
        "instagram": "#e4405f",
        "x": "#1da1f2",
        "linkedin": "#0a66c2",
    }.get(platform, "#8b949e")


def _build_report_html(
    business: Business,
    current: dict,
    previous: dict,
    platforms: dict,
    posts: list,
    period_label: str,
    total_posts: int,
    total_delivered: int,
    total_failed: int,
) -> str:
    """Build the full HTML email for a business metrics report."""

    # Metric cards with deltas
    cards_row1 = "<tr>"
    for key, label in [("impressions", "Impressions"), ("reach", "Reach"), ("engagement", "Engagements"), ("clicks", "Clicks")]:
        delta = _delta_badge(current[key], previous[key])
        cards_row1 += _build_metric_card(label, current[key], delta)
    cards_row1 += "</tr>"

    cards_row2 = "<tr>"
    for key, label in [("likes", "Likes"), ("comments", "Comments"), ("shares", "Shares"), ("saves", "Saves")]:
        delta = _delta_badge(current[key], previous[key])
        cards_row2 += _build_metric_card(label, current[key], delta)
    cards_row2 += "</tr>"

    # Platform breakdown rows
    platform_rows = ""
    for plat, data in sorted(platforms.items()):
        color = _platform_color(plat)
        platform_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;">
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;background:{color};color:#fff;font-size:11px;font-weight:600;">{plat.title()}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;text-align:center;color:#c9d1d9;">{_fmt(data['impressions'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;text-align:center;color:#c9d1d9;">{_fmt(data['likes'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;text-align:center;color:#c9d1d9;">{_fmt(data['comments'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;text-align:center;color:#c9d1d9;">{_fmt(data['shares'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #21262d;text-align:center;color:#c9d1d9;font-weight:bold;">{_fmt(data['engagement'])}</td>
        </tr>"""

    if not platform_rows:
        platform_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#484f58;">No platform data available yet</td></tr>'

    # Recent posts
    post_rows = ""
    for post in posts[:10]:
        date_str = post.created_at.strftime("%b %d, %H:%M")
        content_preview = post.content_text[:80] + ("..." if len(post.content_text) > 80 else "")
        content_preview = content_preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Delivery badges
        delivery_badges = ""
        post_engagement = 0
        post_impressions = 0
        for d in post.deliveries:
            color = "#2ea043" if d.status == "delivered" else "#da3633"
            icon = "✓" if d.status == "delivered" else "✗"
            plat_color = _platform_color(d.platform)
            delivery_badges += f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;background:{plat_color};color:#fff;font-size:10px;margin-right:3px;">{d.platform} {icon}</span>'
            if d.metrics:
                post_engagement += d.metrics.engagement
                post_impressions += d.metrics.impressions

        engagement_str = f"{_fmt(post_impressions)} views · {_fmt(post_engagement)} eng" if post_impressions > 0 or post_engagement > 0 else "—"

        post_rows += f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;font-size:12px;color:#8b949e;white-space:nowrap;">{date_str}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;font-size:12px;color:#c9d1d9;">{content_preview}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;font-size:11px;">{delivery_badges}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;font-size:12px;color:#58a6ff;text-align:right;white-space:nowrap;">{engagement_str}</td>
        </tr>"""

    if not post_rows:
        post_rows = '<tr><td colspan="4" style="padding:16px;text-align:center;color:#484f58;">No posts in this period</td></tr>'

    now_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;background:#0d1117;color:#e1e4e8;">

      <!-- Header -->
      <div style="background:linear-gradient(135deg,#161b22,#1c2333);padding:24px 28px;border-bottom:3px solid #58a6ff;">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
          <td>
            <h1 style="margin:0;font-size:22px;color:#58a6ff;">📊 Performance Report</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#8b949e;">{business.name} · {period_label} · {now_str}</p>
          </td>
          <td style="text-align:right;vertical-align:top;">
            <span style="display:inline-block;padding:4px 12px;border-radius:12px;background:#21262d;color:#58a6ff;font-size:12px;font-weight:600;">SocialAutoPost</span>
          </td>
        </tr></table>
      </div>

      <div style="padding:24px 28px;">

        <!-- Quick Stats -->
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:20px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#2ea043;">{total_posts}</div>
              <div style="font-size:11px;color:#8b949e;">Posts Created</div>
            </td>
            <td style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:#58a6ff;">{total_delivered}</div>
              <div style="font-size:11px;color:#8b949e;">Delivered</div>
            </td>
            <td style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:{'#da3633' if total_failed > 0 else '#2ea043'};">{total_failed}</div>
              <div style="font-size:11px;color:#8b949e;">Failed</div>
            </td>
          </tr></table>
        </div>

        <!-- Engagement Metrics -->
        <h2 style="font-size:16px;color:#c9d1d9;margin:20px 0 12px;border-bottom:1px solid #21262d;padding-bottom:8px;">Engagement Metrics</h2>
        <table width="100%" cellpadding="4" cellspacing="8" style="border-collapse:separate;">
          {cards_row1}
        </table>
        <table width="100%" cellpadding="4" cellspacing="8" style="border-collapse:separate;margin-top:8px;">
          {cards_row2}
        </table>

        <!-- Platform Breakdown -->
        <h2 style="font-size:16px;color:#c9d1d9;margin:24px 0 12px;border-bottom:1px solid #21262d;padding-bottom:8px;">Platform Breakdown</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;border:1px solid #30363d;border-radius:8px;overflow:hidden;">
          <tr style="background:#161b22;">
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#8b949e;">Platform</th>
            <th style="padding:8px 12px;text-align:center;font-size:11px;color:#8b949e;">Impressions</th>
            <th style="padding:8px 12px;text-align:center;font-size:11px;color:#8b949e;">Likes</th>
            <th style="padding:8px 12px;text-align:center;font-size:11px;color:#8b949e;">Comments</th>
            <th style="padding:8px 12px;text-align:center;font-size:11px;color:#8b949e;">Shares</th>
            <th style="padding:8px 12px;text-align:center;font-size:11px;color:#8b949e;">Total Eng.</th>
          </tr>
          {platform_rows}
        </table>

        <!-- Recent Posts -->
        <h2 style="font-size:16px;color:#c9d1d9;margin:24px 0 12px;border-bottom:1px solid #21262d;padding-bottom:8px;">Recent Posts</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;border:1px solid #30363d;border-radius:8px;overflow:hidden;">
          <tr style="background:#161b22;">
            <th style="padding:8px 10px;text-align:left;font-size:11px;color:#8b949e;">Date</th>
            <th style="padding:8px 10px;text-align:left;font-size:11px;color:#8b949e;">Content</th>
            <th style="padding:8px 10px;text-align:left;font-size:11px;color:#8b949e;">Platforms</th>
            <th style="padding:8px 10px;text-align:right;font-size:11px;color:#8b949e;">Engagement</th>
          </tr>
          {post_rows}
        </table>

        <!-- Business Info -->
        <div style="margin-top:24px;padding:16px;background:#161b22;border:1px solid #30363d;border-radius:8px;">
          <p style="margin:0;font-size:12px;color:#8b949e;">
            <strong style="color:#c9d1d9;">{business.name}</strong> · {business.industry} · {business.location or 'N/A'}<br>
            {('Phone: ' + business.phone + ' · ') if business.phone else ''}
            {('Website: ' + business.website_url) if business.website_url else ''}
          </p>
        </div>

      </div>

      <!-- Footer -->
      <div style="background:#161b22;padding:16px 28px;text-align:center;border-top:1px solid #30363d;">
        <p style="margin:0;font-size:11px;color:#484f58;">
          This report is auto-generated by SocialAutoPost · Metrics updated every 6 hours<br>
          Reply to this email or contact us for questions about this report.
        </p>
      </div>

    </div>
    """


async def send_daily_reports():
    """Generate and send a daily metrics report for each active business."""
    if not settings.resend_api_key:
        log.debug("Resend not configured — skipping daily reports")
        return

    now = datetime.now(timezone.utc)
    # Current period: last 30 days
    current_start = now - timedelta(days=30)
    # Previous period: 30-60 days ago (for comparison deltas)
    previous_start = now - timedelta(days=60)
    previous_end = current_start

    async with async_session() as db:
        # Get all active businesses
        result = await db.execute(
            select(Business).where(Business.is_active == True)
        )
        businesses = result.scalars().all()

        for biz in businesses:
            try:
                # Get metrics for current and previous periods
                current = await _get_period_metrics(db, biz.id, current_start, now)
                previous = await _get_period_metrics(db, biz.id, previous_start, previous_end)

                # Platform breakdown for current period
                platforms = await _get_platform_breakdown(db, biz.id, current_start, now)

                # Recent posts
                posts = await _get_recent_posts(db, biz.id, current_start, now)

                # Post / delivery counts
                total_posts = len(posts)
                total_delivered = sum(
                    1 for p in posts for d in p.deliveries if d.status == "delivered"
                )
                total_failed = sum(
                    1 for p in posts for d in p.deliveries if d.status == "failed"
                )

                # Build and send the email
                html = _build_report_html(
                    business=biz,
                    current=current,
                    previous=previous,
                    platforms=platforms,
                    posts=posts,
                    period_label="Last 30 Days",
                    total_posts=total_posts,
                    total_delivered=total_delivered,
                    total_failed=total_failed,
                )

                subject = f"📊 {biz.name} — Daily Performance Report ({now.strftime('%b %d, %Y')})"
                from_email = settings.smtp_from or "notifications@rickysautomations.com"

                payload = {
                    "from": from_email,
                    "to": [settings.notification_email],
                    "subject": subject,
                    "html": html,
                }

                headers = {
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                }

                resp = httpx.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)
                if resp.status_code in (200, 201):
                    log.info(f"Daily report sent for {biz.name} to {settings.notification_email}")
                else:
                    log.error(f"Daily report failed for {biz.name}: {resp.status_code} {resp.text}")

            except Exception as e:
                log.error(f"Failed to generate daily report for {biz.name}: {e}")

    log.info("Daily report cycle complete")
