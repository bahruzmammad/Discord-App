"""Tests for the ranking engine."""

import pytest
from datetime import datetime, timezone, timedelta
from models.article import Article, Category
from core.ranker import Ranker, _recency_score, _credibility_score, _keyword_boost


def make_article(
    title: str = "Test Article",
    source: str = "Unknown",
    category: Category = Category.TECH_NEWS,
    hours_old: float = 1.0,
    raw_score: float = 0.0,
    summary: str = "",
) -> Article:
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
        category=category,
        timestamp=ts,
        summary=summary or None,
        raw_score=raw_score,
        provider="test",
    )


class TestRecencyScore:
    def test_very_recent(self):
        ts = datetime.now(timezone.utc) - timedelta(minutes=5)
        score = _recency_score(ts)
        assert score > 0.95

    def test_one_day_old(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=24)
        score = _recency_score(ts)
        assert 0.4 < score < 0.6  # half-life at 24h → ~0.5

    def test_week_old(self):
        ts = datetime.now(timezone.utc) - timedelta(days=7)
        score = _recency_score(ts)
        assert score < 0.05  # very decayed

    def test_future_timestamp(self):
        ts = datetime.now(timezone.utc) + timedelta(hours=1)
        score = _recency_score(ts)
        assert score <= 1.0


class TestCredibilityScore:
    def test_arxiv_high(self):
        assert _credibility_score("arXiv cs.AI") > 0.9

    def test_nvd_high(self):
        # Source credibility key is "nvd.nist" — must be a substring of the source name
        assert _credibility_score("nvd.nist.gov") > 0.9

    def test_unknown_baseline(self):
        score = _credibility_score("SomeRandomBlog")
        assert 0.4 < score < 0.7

    def test_case_insensitive(self):
        a = _credibility_score("GitHub Trending")
        b = _credibility_score("github trending")
        assert a == b


class TestKeywordBoost:
    def test_critical_cve_boost(self):
        a = make_article(
            title="Critical RCE zero-day vulnerability in OpenSSL",
            summary="Researchers discovered a critical remote code execution flaw.",
        )
        boost = _keyword_boost(a)
        assert boost > 0.1

    def test_no_keywords(self):
        a = make_article(title="A company published a blog post about their office")
        boost = _keyword_boost(a)
        assert boost == pytest.approx(0.0)

    def test_max_cap(self):
        a = make_article(
            title="Critical exploit critical exploit critical exploit critical exploit"
        )
        boost = _keyword_boost(a)
        assert boost <= 0.3


class TestRanker:
    def setup_method(self):
        self.ranker = Ranker()

    def test_scores_assigned(self):
        articles = [make_article() for _ in range(5)]
        ranked = self.ranker.rank(articles)
        for a in ranked:
            assert 0.0 <= a.relevance_score <= 1.0

    def test_sorted_descending(self):
        articles = [
            make_article(source="arXiv cs.AI", hours_old=1),
            make_article(source="SomeRandomBlog", hours_old=48),
        ]
        ranked = self.ranker.rank(articles)
        scores = [a.relevance_score for a in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_recent_arxiv_beats_old_blog(self):
        recent_arxiv = make_article(source="arXiv cs.AI", hours_old=2, raw_score=100)
        old_blog = make_article(source="RandomBlog", hours_old=72, raw_score=5)
        ranked = self.ranker.rank([old_blog, recent_arxiv])
        assert ranked[0].source == "arXiv cs.AI"

    def test_empty_input(self):
        assert self.ranker.rank([]) == []
