"""
Aggregation engine — orchestrates all providers and merges results.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Type

from models.article import Article
from providers.base import BaseProvider
from providers.github_provider import GitHubTrendingProvider
from providers.news_provider import NewsProvider
from providers.reddit_provider import RedditProvider
from providers.rss_provider import RSSProvider
from providers.security_provider import SecurityProvider

logger = logging.getLogger(__name__)

# All registered provider classes — add new ones here
_PROVIDER_CLASSES: List[Type[BaseProvider]] = [
    RSSProvider,
    GitHubTrendingProvider,
    RedditProvider,
    SecurityProvider,
    NewsProvider,
]


class Aggregator:
    """
    Instantiates all providers and runs them concurrently.
    Returns the merged, unsorted, unfiltered list of Article objects.
    """

    def __init__(self, extra_providers: List[BaseProvider] | None = None) -> None:
        self._providers: List[BaseProvider] = [cls() for cls in _PROVIDER_CLASSES]
        if extra_providers:
            self._providers.extend(extra_providers)
        logger.info("Aggregator initialised with %d providers", len(self._providers))

    async def collect(self) -> List[Article]:
        """
        Run all providers concurrently.

        Returns:
            Flat list of all collected Articles (may contain duplicates).
        """
        logger.info("Starting collection cycle across %d providers", len(self._providers))
        tasks = [
            asyncio.create_task(p.safe_fetch(), name=f"provider:{p.name}")
            for p in self._providers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles: List[Article] = []
        for provider, result in zip(self._providers, results):
            if isinstance(result, Exception):
                logger.error("Provider %s raised: %s", provider.name, result)
            else:
                logger.debug("Provider %s → %d items", provider.name, len(result))
                all_articles.extend(result)

        logger.info("Collection complete: %d total items", len(all_articles))
        return all_articles
