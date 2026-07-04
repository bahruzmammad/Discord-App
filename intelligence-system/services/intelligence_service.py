"""
Intelligence service — top-level orchestrator.

Wires the pipeline to the bot and exposes the two main actions:
- deliver_digest(): full daily digest
- deliver_alert(): trending alert (compact, top-N)

Used by both the scheduler (background jobs) and the run-once mode.
"""

from __future__ import annotations

import logging
from typing import Optional

from bot.formatter import format_plain_digest
from config.settings import settings
from core.pipeline import IntelligencePipeline

logger = logging.getLogger(__name__)


class IntelligenceService:
    """
    Orchestrates the pipeline → formatter → bot delivery chain.

    Args:
        pipeline: IntelligencePipeline instance.
        bot:      IntelligenceBot instance (optional in DRY_RUN mode).
    """

    def __init__(self, pipeline: IntelligencePipeline, bot: Optional[object] = None) -> None:
        self.pipeline = pipeline
        self.bot = bot

    async def deliver_digest(self) -> None:
        """Run the full pipeline and deliver the digest to Discord."""
        logger.info("=== DIGEST CYCLE START ===")

        report = await self.pipeline.run()

        if settings.dry_run:
            plain = format_plain_digest(report)
            logger.info("DRY RUN — digest output:\n%s", plain)
            return

        if self.bot is None:
            logger.error("Bot not configured — cannot deliver digest")
            return

        success = await self.bot.send_digest(report)  # type: ignore[union-attr]
        if success:
            logger.info(
                "=== DIGEST DELIVERED — %d articles in %d sections ===",
                report.total_in_digest, len(report.sections),
            )
        else:
            logger.error("=== DIGEST DELIVERY FAILED ===")

    async def deliver_alert(self, top_n: int = 5) -> None:
        """Run a lightweight collection cycle and send a trending alert."""
        logger.info("=== ALERT CYCLE START ===")

        articles = await self.pipeline.run_articles_only()
        if not articles:
            logger.info("No articles — skipping alert")
            return

        top_articles = articles[:top_n]

        if settings.dry_run:
            logger.info("DRY RUN — alert would post %d articles:", top_n)
            for i, a in enumerate(top_articles, 1):
                logger.info("  %d. [%.3f] %s", i, a.relevance_score, a.title)
            return

        if self.bot is None:
            logger.error("Bot not configured — cannot deliver alert")
            return

        await self.bot.send_alert(top_articles, top_n=top_n)  # type: ignore[union-attr]
        logger.info("=== ALERT DELIVERED ===")
