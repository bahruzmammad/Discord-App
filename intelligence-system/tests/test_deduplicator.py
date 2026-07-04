"""Tests for the deduplication engine."""

import pytest
from datetime import datetime, timezone
from models.article import Article, Category
from core.deduplicator import Deduplicator, _jaccard, _tokenise


def make_article(title: str, url: str, score: float = 0.0) -> Article:
    return Article(
        title=title,
        url=url,
        source="Test",
        category=Category.TECH_NEWS,
        timestamp=datetime.now(timezone.utc),
        raw_score=score,
        provider="test",
    )


class TestTokenise:
    def test_basic_tokenisation(self):
        tokens = _tokenise("Python 3.12 released today")
        assert "python" in tokens
        assert "released" in tokens
        assert "today" in tokens
        # Stopwords removed
        assert "the" not in tokens

    def test_short_tokens_excluded(self):
        tokens = _tokenise("AI is a big deal")
        assert "ai" not in tokens  # len < 3
        assert "big" in tokens
        assert "deal" in tokens

    def test_empty_string(self):
        assert _tokenise("") == set()  # _tokenise returns Set[str]


class TestJaccard:
    def test_identical_sets(self):
        a = {"python", "release"}
        assert _jaccard(a, a) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_partial_overlap(self):
        sim = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert 0.4 < sim < 0.6  # 2/4 = 0.5

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == pytest.approx(0.0)
        assert _jaccard({"a"}, set()) == pytest.approx(0.0)


class TestDeduplicator:
    def setup_method(self):
        self.dedup = Deduplicator(threshold=0.75)

    def test_exact_url_dedup_keeps_highest_score(self):
        a1 = make_article("Article One", "https://example.com/article1", score=5)
        a2 = make_article("Article One Different Title", "https://example.com/article1", score=10)
        result = self.dedup.deduplicate([a1, a2])
        assert len(result) == 1
        assert result[0].raw_score == 10  # must keep the highest-scoring copy

    def test_exact_url_dedup_keeps_highest_when_reversed(self):
        # Ensure order-independence: highest score wins regardless of input order
        a_low = make_article("Article Low Score", "https://example.com/same-url", score=1)
        a_high = make_article("Article High Score", "https://example.com/same-url", score=99)
        result1 = self.dedup.deduplicate([a_low, a_high])
        result2 = self.dedup.deduplicate([a_high, a_low])
        assert result1[0].raw_score == 99
        assert result2[0].raw_score == 99

    def test_url_with_utm_dedup(self):
        a1 = make_article("Title", "https://example.com/article?utm_source=twitter")
        a2 = make_article("Title", "https://example.com/article?utm_medium=social")
        result = self.dedup.deduplicate([a1, a2])
        assert len(result) == 1

    def test_fuzzy_title_dedup(self):
        a1 = make_article(
            "Python 3.12 officially released with major performance improvements",
            "https://source1.com/python312",
        )
        a2 = make_article(
            "Python 3.12 released with major performance improvements today",
            "https://source2.com/python312-release",
        )
        result = self.dedup.deduplicate([a1, a2])
        assert len(result) == 1

    def test_different_articles_kept(self):
        a1 = make_article("Python 3.12 released", "https://example.com/a1")
        a2 = make_article("Rust 2024 edition announced", "https://example.com/a2")
        a3 = make_article("Linux kernel 6.7 released", "https://example.com/a3")
        result = self.dedup.deduplicate([a1, a2, a3])
        assert len(result) == 3

    def test_empty_input(self):
        assert self.dedup.deduplicate([]) == []

    def test_single_item(self):
        a = make_article("Only article", "https://example.com/only")
        assert self.dedup.deduplicate([a]) == [a]
