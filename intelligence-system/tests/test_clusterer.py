"""Tests for the topic clustering engine."""

import pytest
from datetime import datetime, timezone
from models.article import Article, Category
from core.clusterer import Clusterer, _tokens, _cosine, _tfidf_vector


def make_article(title: str, summary: str = "") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '_')}",
        source="Test",
        category=Category.TECH_NEWS,
        timestamp=datetime.now(timezone.utc),
        summary=summary or None,
        provider="test",
    )


class TestTokens:
    def test_filters_stopwords(self):
        toks = _tokens("the quick brown fox jumps over the lazy dog")
        assert "the" not in toks
        assert "over" not in toks
        assert "quick" in toks
        assert "brown" in toks

    def test_minimum_length(self):
        toks = _tokens("AI ML DL deep learning")
        # "AI", "ML", "DL" should be filtered (len < 3)
        assert "ai" not in toks
        assert "deep" in toks
        assert "learning" in toks


class TestClustering:
    def setup_method(self):
        self.clusterer = Clusterer(threshold=0.30)

    def test_single_article_gets_cluster(self):
        a = make_article("Python 3.12 released")
        result = self.clusterer.cluster([a])
        assert result[0].cluster_id is not None

    def test_related_articles_same_cluster(self):
        # Use titles with many shared high-signal tokens to ensure cosine >= 0.30
        a1 = make_article(
            "critical remote code execution vulnerability discovered linux kernel patched",
            "Researchers discovered critical remote code execution vulnerability in linux kernel.",
        )
        a2 = make_article(
            "critical remote code execution vulnerability found linux kernel security patch",
            "Security teams report critical remote code execution vulnerability in linux kernel.",
        )
        result = self.clusterer.cluster([a1, a2])
        assert result[0].cluster_id == result[1].cluster_id

    def test_unrelated_articles_different_clusters(self):
        a1 = make_article(
            "Rust programming language memory safety features",
            "The Rust language ensures memory safety without garbage collection.",
        )
        a2 = make_article(
            "Critical CVE vulnerability in Apache HTTP server",
            "A remote code execution vulnerability was discovered in Apache.",
        )
        result = self.clusterer.cluster([a1, a2])
        assert result[0].cluster_id != result[1].cluster_id

    def test_all_articles_get_cluster_id(self):
        articles = [make_article(f"Article {i} about different things") for i in range(10)]
        result = self.clusterer.cluster(articles)
        for a in result:
            assert a.cluster_id is not None

    def test_empty_input(self):
        assert self.clusterer.cluster([]) == []
