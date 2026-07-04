"""Tests for providers/base.py — BaseProvider contract and safe_fetch isolation."""

from __future__ import annotations

import pytest
from typing import List

from models.article import Article, Category
from providers.base import BaseProvider
from models.article import utcnow


def _make_article(title: str = "Test") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        source="Test Source",
        category=Category.TECH_NEWS,
        timestamp=utcnow(),
        provider="test",
    )


class GoodProvider(BaseProvider):
    """Provider that always succeeds."""
    name = "good"

    async def fetch(self) -> List[Article]:
        return [_make_article("Article A"), _make_article("Article B")]


class EmptyProvider(BaseProvider):
    """Provider that always returns empty."""
    name = "empty"

    async def fetch(self) -> List[Article]:
        return []


class CrashingProvider(BaseProvider):
    """Provider that always raises."""
    name = "crashing"

    async def fetch(self) -> List[Article]:
        raise RuntimeError("network is down")


class SlowCrashProvider(BaseProvider):
    """Provider that raises a non-standard exception."""
    name = "slow_crash"

    async def fetch(self) -> List[Article]:
        raise ValueError("malformed RSS feed")


class TestBaseProviderContract:
    def test_name_attribute_required(self):
        """Each provider class must define a name attribute."""
        assert GoodProvider.name == "good"
        assert EmptyProvider.name == "empty"
        assert CrashingProvider.name == "crashing"

    def test_logger_namespaced_by_provider(self):
        p = GoodProvider()
        assert p.logger.name == "providers.good"

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]


class TestSafeFetch:
    @pytest.mark.asyncio
    async def test_good_provider_returns_articles(self):
        articles = await GoodProvider().safe_fetch()
        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)

    @pytest.mark.asyncio
    async def test_empty_provider_returns_empty_list(self):
        articles = await EmptyProvider().safe_fetch()
        assert articles == []

    @pytest.mark.asyncio
    async def test_crashing_provider_returns_empty_not_raises(self):
        """safe_fetch must absorb any exception and return []."""
        articles = await CrashingProvider().safe_fetch()
        assert articles == []

    @pytest.mark.asyncio
    async def test_value_error_also_absorbed(self):
        articles = await SlowCrashProvider().safe_fetch()
        assert articles == []

    @pytest.mark.asyncio
    async def test_safe_fetch_result_is_list(self):
        result = await GoodProvider().safe_fetch()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_articles_have_correct_types(self):
        articles = await GoodProvider().safe_fetch()
        for a in articles:
            assert isinstance(a.title, str)
            assert isinstance(a.url, str)
            assert isinstance(a.category, Category)
