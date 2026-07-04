"""Tests for the digest builder."""

import pytest
from datetime import datetime, timezone
from models.article import Article, Category
from core.digest import DigestBuilder, DIGEST_CATEGORY_ORDER


def make_article(category: Category, score: float, title: str = "") -> Article:
    return Article(
        title=title or f"Article {score:.2f} [{category.value}]",
        url=f"https://example.com/{score}-{category.value}",
        source="Test",
        category=category,
        timestamp=datetime.now(timezone.utc),
        relevance_score=score,
        provider="test",
    )


class TestDigestBuilder:
    def setup_method(self):
        self.builder = DigestBuilder(top_n=5, min_score=0.2)

    def test_empty_input(self):
        report = self.builder.build([])
        assert report.total_in_digest == 0
        assert report.sections == []

    def test_filters_low_score(self):
        articles = [
            make_article(Category.TECH_NEWS, 0.1),
            make_article(Category.TECH_NEWS, 0.5),
        ]
        report = self.builder.build(articles)
        assert report.total_in_digest == 1

    def test_top_n_per_category(self):
        articles = [make_article(Category.PROGRAMMING, 0.8 - i * 0.05) for i in range(10)]
        report = self.builder.build(articles)
        programming_section = next(
            (s for s in report.sections if s.category == Category.PROGRAMMING), None
        )
        assert programming_section is not None
        assert len(programming_section.articles) == 5  # top_n=5

    def test_category_order(self):
        articles = []
        for cat in [Category.PROGRAMMING, Category.TECH_NEWS, Category.CYBERSECURITY]:
            articles.append(make_article(cat, 0.8))
        report = self.builder.build(articles)
        section_categories = [s.category for s in report.sections]
        # Verify sections appear in DIGEST_CATEGORY_ORDER order
        indices = [DIGEST_CATEGORY_ORDER.index(c) for c in section_categories]
        assert indices == sorted(indices)

    def test_generated_at_is_utc(self):
        report = self.builder.build([make_article(Category.TECH_NEWS, 0.8)])
        assert report.generated_at.tzinfo is not None

    def test_counts_accurate(self):
        articles = [make_article(Category.TECH_NEWS, 0.8) for _ in range(3)]
        report = self.builder.build(articles, total_collected=100, total_after_dedup=50)
        assert report.total_collected == 100
        assert report.total_after_dedup == 50
        assert report.total_in_digest == 3

    def test_all_articles_property(self):
        articles = [
            make_article(Category.TECH_NEWS, 0.8),
            make_article(Category.PROGRAMMING, 0.7),
        ]
        report = self.builder.build(articles)
        assert len(report.all_articles) == 2
