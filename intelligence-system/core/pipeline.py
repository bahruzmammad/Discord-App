"""
Core pipeline — wires together Aggregator → Deduplicator → Ranker → Clusterer → DigestBuilder.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from config.settings import settings
from core.aggregator import Aggregator
from core.clusterer import Clusterer
from core.deduplicator import Deduplicator
from core.digest import DigestBuilder, DigestReport
from core.ranker import Ranker
from models.article import Article

logger = logging.getLogger(__name__)


class IntelligencePipeline:
    """
    End-to-end processing pipeline.

    Usage:
        pipeline = IntelligencePipeline()
        report = await pipeline.run()
    """

    def __init__(self) -> None:
        self.aggregator = Aggregator()
        self.deduplicator = Deduplicator(threshold=settings.collector.dedup_threshold)
        self.ranker = Ranker()
        self.clusterer = Clusterer()
        self.digest_builder = DigestBuilder()

    async def run(self) -> DigestReport:
        """Execute the full collection → processing → digest pipeline."""
        # 1. Collect
        raw_articles = await self.aggregator.collect()
        total_collected = len(raw_articles)
        logger.info("Pipeline step 1/5 — collected %d raw articles", total_collected)

        # 2. Deduplicate
        deduped = self.deduplicator.deduplicate(raw_articles)
        total_deduped = len(deduped)
        logger.info("Pipeline step 2/5 — %d articles after dedup", total_deduped)

        # 3. Rank
        ranked = self.ranker.rank(deduped)
        logger.info("Pipeline step 3/5 — ranked %d articles", len(ranked))

        # 4. Cluster
        clustered = self.clusterer.cluster(ranked)
        logger.info("Pipeline step 4/5 — clustered into topics")

        # 5. Build digest
        report = self.digest_builder.build(
            clustered,
            total_collected=total_collected,
            total_after_dedup=total_deduped,
        )
        logger.info(
            "Pipeline step 5/5 — digest ready: %d sections, %d articles",
            len(report.sections), report.total_in_digest,
        )
        return report

    async def run_articles_only(self) -> List[Article]:
        """Run pipeline through ranking without building a digest (for alerts)."""
        raw = await self.aggregator.collect()
        deduped = self.deduplicator.deduplicate(raw)
        ranked = self.ranker.rank(deduped)
        return ranked
