"""Tests for core/aggregator.py — provider orchestration and result merging."""

from __future__ import annotations

import pytest
from typing import List

from core.aggregator import Aggregator
from models.article import Article, Category
from providers.base import BaseProvider
from models.article import utcnow


def _article(title: str, provider: str = "test") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        source="Test",
        category=Category.TECH_NEWS,
        timestamp=utcnow(),
        provider=provider,
    )


class FixedProvider(BaseProvider):
    """Returns a fixed list of articles."""
    name = "fixed"

    def __init__(self, articles: List[Article], name: str = "fixed") -> None:
        self.name = name
        self._articles = articles
        super().__init__()

    async def fetch(self) -> List[Article]:
        return self._articles


class AlwaysFailProvider(BaseProvider):
    name = "fail"

    async def fetch(self) -> List[Article]:
        raise ConnectionError("simulated network failure")


class TestAggregatorInit:
    def test_extra_providers_added(self):
        p = FixedProvider([], "extra")
        agg = Aggregator(extra_providers=[p])
        names = [prov.name for prov in agg._providers]
        assert "extra" in names

    def test_extra_providers_none_safe(self):
        agg = Aggregator(extra_providers=None)
        assert isinstance(agg._providers, list)
        assert len(agg._providers) >= 1


class TestAggregatorCollect:
    @pytest.mark.asyncio
    async def test_collect_merges_results_from_all_providers(self):
        p1 = FixedProvider([_article("A"), _article("B")], "p1")
        p2 = FixedProvider([_article("C")], "p2")
        agg = Aggregator(extra_providers=[])
        agg._providers = [p1, p2]

        articles = await agg.collect()
        titles = {a.title for a in articles}
        assert titles == {"A", "B", "C"}

    @pytest.mark.asyncio
    async def test_collect_returns_list(self):
        p = FixedProvider([_article("X")], "px")
        agg = Aggregator(extra_providers=[])
        agg._providers = [p]
        result = await agg.collect()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_failing_provider_does_not_crash_aggregator(self):
        good = FixedProvider([_article("Good")], "good")
        bad = AlwaysFailProvider()
        agg = Aggregator(extra_providers=[])
        agg._providers = [good, bad]

        articles = await agg.collect()
        # Good provider's articles still come through
        assert any(a.title == "Good" for a in articles)

    @pytest.mark.asyncio
    async def test_all_failing_providers_returns_empty(self):
        agg = Aggregator(extra_providers=[])
        agg._providers = [AlwaysFailProvider(), AlwaysFailProvider()]
        articles = await agg.collect()
        assert articles == []

    @pytest.mark.asyncio
    async def test_empty_providers_returns_empty(self):
        agg = Aggregator(extra_providers=[])
        agg._providers = []
        articles = await agg.collect()
        assert articles == []

    @pytest.mark.asyncio
    async def test_articles_preserve_provider_field(self):
        p = FixedProvider([_article("Z", provider="my_provider")], "my_provider")
        agg = Aggregator(extra_providers=[])
        agg._providers = [p]
        articles = await agg.collect()
        assert articles[0].provider == "my_provider"

    @pytest.mark.asyncio
    async def test_all_providers_results_merged(self):
        """Results from every provider are combined into a single flat list."""
        providers = [FixedProvider([_article(f"Article-{i}")], f"p{i}") for i in range(5)]
        agg = Aggregator(extra_providers=[])
        agg._providers = providers
        articles = await agg.collect()
        assert len(articles) == 5
        titles = {a.title for a in articles}
        assert titles == {f"Article-{i}" for i in range(5)}
