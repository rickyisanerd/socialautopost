import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.core.config import settings
from app.core.orchestrator import run_post_cycle
from app.core.metrics import collect_metrics
from app.core.reports import send_daily_reports

log = logging.getLogger("socialautopost")

scheduler = AsyncIOScheduler()

DAY_MAP = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
}


def start_scheduler():
    days = settings.posting_days.lower().split(",")
    cron_days = ",".join(DAY_MAP.get(d.strip(), d.strip()) for d in days)

    hour, minute = settings.posting_time.split(":")

    trigger = CronTrigger(
        day_of_week=cron_days,
        hour=int(hour),
        minute=int(minute),
        timezone=settings.timezone,
    )

    scheduler.add_job(
        _run_cycle,
        trigger=trigger,
        id="auto_post_cycle",
        replace_existing=True,
        name="Auto Post Cycle",
    )

    # Metrics collection — every 6 hours
    scheduler.add_job(
        _collect_metrics,
        trigger=IntervalTrigger(hours=6),
        id="metrics_collection",
        replace_existing=True,
        name="Metrics Collection",
    )

    # Daily metrics report emails — 8:00 AM Central every day
    scheduler.add_job(
        _send_daily_reports,
        trigger=CronTrigger(hour=8, minute=0, timezone=settings.timezone),
        id="daily_reports",
        replace_existing=True,
        name="Daily Reports",
    )

    scheduler.start()
    log.info(f"Scheduler started: posting on {cron_days} at {settings.posting_time} {settings.timezone}")
    log.info("Metrics collection scheduled every 6 hours")
    log.info("Daily reports scheduled at 8:00 AM Central")


async def _run_cycle():
    log.info("Scheduled post cycle starting")
    try:
        await run_post_cycle()
    except Exception as e:
        log.error(f"Scheduled post cycle failed: {e}")


async def _collect_metrics():
    log.info("Scheduled metrics collection starting")
    try:
        await collect_metrics()
    except Exception as e:
        log.error(f"Scheduled metrics collection failed: {e}")


async def _send_daily_reports():
    log.info("Daily report emails starting")
    try:
        await send_daily_reports()
    except Exception as e:
        log.error(f"Daily report emails failed: {e}")
