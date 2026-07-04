"""
Digest generator — selects the top articles per category and builds the
structured intelligence report as a list of DigestSection objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from config.settings import settings
from models.article import Article, Category, utcnow

logger = logging.getLogger(__name__)

# Ordered category sequence for the digest
DIGEST_CATEGORY_ORDER: List[Category] = [
    Category.TECH_NEWS,
    Category.PROGRAMMING,
    Category.CS_RESEARCH,
    Category.CYBERSECURITY,
    Category.OSINT,
    Category.OPEN_SOURCE,
]


@dataclass
class DigestSection:
    """One section of the daily digest — a category with its top articles."""
    category: Category
    articles: List[Article]

    @property
    def label(self) -> str:
        return Category.label(self.category)

    @property
    def emoji(self) -> str:
        return Category.emoji(self.category)


@dataclass
class DigestReport:
    """The complete daily intelligence report."""
    generated_at: datetime
    sections: List[DigestSection]
    total_collected: int
    total_after_dedup: int
    total_in_digest: int

    @property
    def all_articles(self) -> List[Article]:
        return [a for s in self.sections for a in s.articles]


class DigestBuilder:
    """
    Selects top-N articles per category and assembles a DigestReport.

    Args:
        top_n: Maximum articles per category section.
        min_score: Articles below this relevance score are excluded.
    """

    def __init__(
        self,
        top_n: int | None = None,
        min_score: float | None = None,
    ) -> None:
        self.top_n = top_n or settings.collector.digest_top_n
        self.min_score = min_score or settings.collector.min_relevance_score

    def build(
        self,
        articles: List[Article],
        total_collected: int = 0,
        total_after_dedup: int = 0,
    ) -> DigestReport:
        """
        Build a digest from a ranked, deduplicated list of articles.

        Args:
            articles:           All articles, already ranked (relevance_score set).
            total_collected:    Raw count before dedup (for the report footer).
            total_after_dedup:  Count after dedup (for the report footer).

        Returns:
            DigestReport ready for formatting and delivery.
        """
        # Filter by minimum score
        qualified = [a for a in articles if a.relevance_score >= self.min_score]
        logger.info(
            "Digest: %d articles qualify (min_score=%.2f) from %d ranked",
            len(qualified), self.min_score, len(articles),
        )

        # Group by category
        by_cat: Dict[Category, List[Article]] = {c: [] for c in DIGEST_CATEGORY_ORDER}
        for article in qualified:
            cat = article.category if article.category in by_cat else None
            if cat:
                by_cat[cat].append(article)

        # Build sections
        sections: List[DigestSection] = []
        total_in_digest = 0
        for category in DIGEST_CATEGORY_ORDER:
            cat_articles = by_cat.get(category, [])
            # Already sorted by relevance_score descending from ranker
            top = cat_articles[: self.top_n]
            if top:
                sections.append(DigestSection(category=category, articles=top))
                total_in_digest += len(top)

        report = DigestReport(
            generated_at=utcnow(),
            sections=sections,
            total_collected=total_collected,
            total_after_dedup=total_after_dedup,
            total_in_digest=total_in_digest,
        )
        logger.info(
            "Digest built: %d sections, %d articles total",
            len(sections), total_in_digest,
        )
        return report
