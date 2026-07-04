"""
Abstract base class for all data providers.
Every provider must implement `fetch()` and return a list of Article objects.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from models.article import Article


class BaseProvider(ABC):
    """
    Contract for all intelligence data providers.

    Subclasses must implement `fetch()`. The engine calls `safe_fetch()` which
    wraps the call with error isolation so a single broken provider never
    stops the overall collection cycle.
    """

    # Human-readable name used in logging and article.provider field
    name: str = "base"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"providers.{self.name}")

    @abstractmethod
    async def fetch(self) -> List[Article]:
        """
        Collect articles from the data source.

        Returns:
            List of normalised Article objects. May be empty.
            Must not raise — use self.logger to report issues and return [].
        """
        ...

    async def safe_fetch(self) -> List[Article]:
        """Fetch with top-level exception isolation — used by the aggregator."""
        try:
            articles = await self.fetch()
            self.logger.info("Fetched %d items", len(articles))
            return articles
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Unhandled error during fetch: %s", exc, exc_info=True)
            return []
