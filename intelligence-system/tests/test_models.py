"""Tests for the Article model."""

import pytest
from datetime import datetime, timezone
from models.article import Article, Category, utcnow


def make_article(**kwargs) -> Article:
    defaults = dict(
        title="Test Article",
        url="https://example.com/test",
        source="Test Source",
        category=Category.TECH_NEWS,
        timestamp=datetime.now(timezone.utc),
        provider="test",
    )
    defaults.update(kwargs)
    return Article(**defaults)


class TestArticle:
    def test_content_id_stable(self):
        a = make_article(url="https://example.com/article")
        assert a.content_id == a.content_id  # idempotent

    def test_content_id_url_normalised(self):
        a1 = make_article(url="https://example.com/article?utm_source=twitter")
        a2 = make_article(url="https://example.com/article?utm_medium=email")
        assert a1.content_id == a2.content_id

    def test_content_id_different_urls(self):
        a1 = make_article(url="https://example.com/article1")
        a2 = make_article(url="https://example.com/article2")
        assert a1.content_id != a2.content_id

    def test_title_fingerprint_lowercased(self):
        a = make_article(title="Python 3.12 RELEASED!!!")
        fp = a.title_fingerprint
        assert fp == fp.lower()
        assert "!" not in fp

    def test_to_dict_keys(self):
        a = make_article()
        d = a.to_dict()
        for key in ("title", "url", "source", "category", "timestamp",
                    "relevance_score", "raw_score", "provider"):
            assert key in d

    def test_to_dict_score_rounded(self):
        a = make_article()
        a.relevance_score = 0.123456789
        d = a.to_dict()
        assert d["relevance_score"] == pytest.approx(0.1235, abs=1e-4)

    def test_repr_contains_title(self):
        a = make_article(title="Breaking news about AI")
        assert "Breaking news" in repr(a)


class TestCategory:
    def test_label_has_emoji(self):
        label = Category.label(Category.CYBERSECURITY)
        assert "🔒" in label

    def test_all_categories_have_labels(self):
        for cat in Category:
            label = Category.label(cat)
            assert label  # non-empty

    def test_emoji_extraction(self):
        emoji = Category.emoji(Category.TECH_NEWS)
        assert emoji  # non-empty


class TestUtcNow:
    def test_returns_utc(self):
        now = utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo.utcoffset(now).total_seconds() == 0
