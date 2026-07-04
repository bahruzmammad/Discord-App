"""Tests for core/pipeline.py — end-to-end pipeline with mocked aggregator."""

from __future__ import annotations

import pytest
from datetime import timezone
from typing import List
from unittest.mock import AsyncMock, patch

from core.pipeline import IntelligencePipeline
from core.digest import DigestReport
from models.article import Article, Category, utcnow


def _make_articles(n: int = 10) -> List[Article]:
    articles = []
    categories = list(Category)
    for i in range(n):
        cat = categories[i % len(categories)]
        articles.append(Article(
            title=f"Unique Article Title Number {i} About Technology",
            url=f"https://example.com/article-{i}",
            source="TechSource",
            category=cat,
            timestamp=utcnow(),
            raw_score=float(i),
            provider="test",
        ))
    return articles


class TestIntelligencePipelineRun:
    @pytest.mark.asyncio
    async def test_run_returns_digest_report(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(20)
            report = await pipeline.run()
        assert isinstance(report, DigestReport)

    @pytest.mark.asyncio
    async def test_run_with_empty_collection_returns_report(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = []
            report = await pipeline.run()
        assert isinstance(report, DigestReport)
        assert report.total_collected == 0
        assert report.total_in_digest == 0

    @pytest.mark.asyncio
    async def test_run_total_collected_matches_provider_output(self):
        pipeline = IntelligencePipeline()
        articles = _make_articles(15)
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = articles
            report = await pipeline.run()
        assert report.total_collected == 15

    @pytest.mark.asyncio
    async def test_run_dedup_reduces_count(self):
        """Identical URLs must be deduped; total_after_dedup ≤ total_collected."""
        pipeline = IntelligencePipeline()
        base = _make_articles(10)
        # Add 5 duplicates
        duplicates = [Article(
            title=a.title,
            url=a.url,
            source=a.source,
            category=a.category,
            timestamp=a.timestamp,
            provider=a.provider,
        ) for a in base[:5]]
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = base + duplicates
            report = await pipeline.run()
        assert report.total_after_dedup <= report.total_collected

    @pytest.mark.asyncio
    async def test_run_digest_sections_non_empty_when_articles_present(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(30)
            report = await pipeline.run()
        assert len(report.sections) >= 1

    @pytest.mark.asyncio
    async def test_run_generated_at_is_utc(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(5)
            report = await pipeline.run()
        assert report.generated_at.tzinfo is not None
        assert report.generated_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_run_aggregator_called_exactly_once(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(5)
            await pipeline.run()
        mock_collect.assert_called_once()


class TestIntelligencePipelineRunArticlesOnly:
    @pytest.mark.asyncio
    async def test_run_articles_only_returns_list(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(10)
            result = await pipeline.run_articles_only()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_run_articles_only_returns_articles(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(10)
            result = await pipeline.run_articles_only()
        assert all(isinstance(a, Article) for a in result)

    @pytest.mark.asyncio
    async def test_run_articles_only_sorted_by_score(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = _make_articles(10)
            result = await pipeline.run_articles_only()
        scores = [a.relevance_score for a in result]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_run_articles_only_empty_input(self):
        pipeline = IntelligencePipeline()
        with patch.object(pipeline.aggregator, "collect", new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = []
            result = await pipeline.run_articles_only()
        assert result == []
