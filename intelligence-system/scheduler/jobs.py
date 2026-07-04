"""
Scheduler layer — manages background jobs using APScheduler.

Jobs:
1. daily_digest  — runs once per day at DIGEST_TIME_UTC
2. trending_alert — runs every ALERT_INTERVAL_HOURS hours (if > 0)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Wraps APScheduler with the specific job definitions for this system.
    Must be started after the event loop is running and the bot is ready.
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._intelligence_service: Optional[object] = None  # set via register()

    def register(self, intelligence_service: object) -> None:
        """Bind the IntelligenceService so jobs can call its methods."""
        self._intelligence_service = intelligence_service

    def start(self) -> None:
        if self._intelligence_service is None:
            raise RuntimeError("Call register(service) before start()")

        # 1. Daily digest job
        h, m = _parse_hhmm(settings.discord.digest_time)
        self._scheduler.add_job(
            self._run_digest,
            trigger=CronTrigger(hour=h, minute=m, timezone="UTC"),
            id="daily_digest",
            name="Daily Intelligence Digest",
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info("Daily digest scheduled at %02d:%02d UTC", h, m)

        # 2. Optional trending alert job
        interval = settings.discord.alert_interval_hours
        if interval > 0:
            self._scheduler.add_job(
                self._run_alert,
                trigger=IntervalTrigger(hours=interval, timezone="UTC"),
                id="trending_alert",
                name="Trending Alert",
                max_instances=1,
                misfire_grace_time=120,
            )
            logger.info("Trending alert scheduled every %d hours", interval)

        self._scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def _run_digest(self) -> None:
        logger.info("[scheduler] Triggering daily digest job")
        try:
            await self._intelligence_service.deliver_digest()  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("[scheduler] Daily digest job failed: %s", exc, exc_info=True)

    async def _run_alert(self) -> None:
        logger.info("[scheduler] Triggering trending alert job")
        try:
            await self._intelligence_service.deliver_alert()  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("[scheduler] Alert job failed: %s", exc, exc_info=True)


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' string into (hour, minute) ints."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        logger.warning("Invalid DIGEST_TIME_UTC '%s', defaulting to 08:00", time_str)
        return 8, 0
