"""Tests for bot/formatter.py — Discord embed generation and plain-text output."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import List

from bot.formatter import (
    _truncate,
    _format_article_line,
    build_digest_header,
    build_section_embeds,
    build_digest_footer,
    build_trending_alert,
    format_plain_digest,
    CATEGORY_COLOURS,
)
from core.digest import DigestReport, DigestSection
from models.article import Article, Category, utcnow


def _article(title: str = "Test Article", category: Category = Category.TECH_NEWS,
             score: float = 0.8, url: str = "https://example.com/test") -> Article:
    a = Article(
        title=title,
        url=url,
        source="TechCrunch",
        category=category,
        timestamp=utcnow(),
        provider="test",
    )
    a.relevance_score = score
    return a


def _report(articles: List[Article] | None = None, n: int = 3) -> DigestReport:
    arts = articles or [_article(f"Article {i}", score=0.9 - i * 0.1) for i in range(n)]
    section = DigestSection(
        category=Category.TECH_NEWS,
        articles=arts,
    )
    return DigestReport(
        sections=[section],
        generated_at=datetime(2026, 7, 4, 8, 0, 0, tzinfo=timezone.utc),
        total_collected=100,
        total_after_dedup=80,
        total_in_digest=len(arts),
    )


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("a" * 100, 20)
        assert len(result) == 20

    def test_truncated_ends_with_suffix(self):
        result = _truncate("a" * 100, 20)
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        s = "a" * 10
        assert _truncate(s, 10) == s

    def test_custom_suffix(self):
        result = _truncate("hello world", 8, suffix="...")
        assert result.endswith("...")
        assert len(result) == 8


class TestFormatArticleLine:
    def test_contains_title(self):
        a = _article("My Article Title")
        line = _format_article_line(a, 1)
        assert "My Article Title" in line

    def test_contains_url(self):
        a = _article(url="https://example.com/my-post")
        line = _format_article_line(a, 1)
        assert "https://example.com/my-post" in line

    def test_contains_index(self):
        a = _article()
        line = _format_article_line(a, 5)
        assert "5." in line

    def test_contains_source(self):
        a = _article()
        line = _format_article_line(a, 1)
        assert "TechCrunch" in line

    def test_summary_appended_when_present(self):
        a = _article()
        a.summary = "This is a summary"
        line = _format_article_line(a, 1)
        assert "This is a summary" in line

    def test_no_summary_no_crash(self):
        a = _article()
        a.summary = None
        line = _format_article_line(a, 1)
        assert isinstance(line, str)


class TestBuildDigestHeader:
    def test_returns_dict(self):
        report = _report()
        result = build_digest_header(report)
        assert isinstance(result, dict)

    def test_has_title(self):
        result = build_digest_header(_report())
        assert "title" in result
        assert "OSINT" in result["title"]

    def test_has_description(self):
        result = build_digest_header(_report())
        assert "description" in result

    def test_description_contains_counts(self):
        result = build_digest_header(_report())
        desc = result["description"]
        assert "100" in desc  # total_collected
        assert "80" in desc   # total_after_dedup

    def test_has_color(self):
        result = build_digest_header(_report())
        assert "color" in result
        assert isinstance(result["color"], int)

    def test_has_footer(self):
        result = build_digest_header(_report())
        assert "footer" in result


class TestBuildSectionEmbeds:
    def test_returns_list(self):
        report = _report()
        embeds = build_section_embeds(report.sections[0])
        assert isinstance(embeds, list)

    def test_at_least_one_embed(self):
        report = _report()
        embeds = build_section_embeds(report.sections[0])
        assert len(embeds) >= 1

    def test_embed_has_fields(self):
        report = _report()
        embed = build_section_embeds(report.sections[0])[0]
        assert "fields" in embed
        assert len(embed["fields"]) > 0

    def test_colour_matches_category(self):
        for cat in Category:
            arts = [_article(category=cat)]
            section = DigestSection(category=cat, articles=arts)
            embeds = build_section_embeds(section)
            expected_colour = CATEGORY_COLOURS.get(cat, 0x95A5A6)
            assert embeds[0]["color"] == expected_colour

    def test_large_section_splits_into_multiple_embeds(self):
        """Sections with > 8 articles must produce multiple embeds."""
        arts = [_article(f"Article {i}", url=f"https://example.com/{i}") for i in range(20)]
        section = DigestSection(category=Category.TECH_NEWS, articles=arts)
        embeds = build_section_embeds(section)
        assert len(embeds) >= 2

    def test_empty_section_returns_empty_list(self):
        section = DigestSection(category=Category.TECH_NEWS, articles=[])
        embeds = build_section_embeds(section)
        assert embeds == []


class TestBuildDigestFooter:
    def test_returns_dict(self):
        result = build_digest_footer(_report())
        assert isinstance(result, dict)

    def test_has_title_and_description(self):
        result = build_digest_footer(_report())
        assert "title" in result
        assert "description" in result

    def test_has_color(self):
        result = build_digest_footer(_report())
        assert "color" in result


class TestBuildTrendingAlert:
    def test_returns_list_of_dicts(self):
        arts = [_article(f"Trending {i}", url=f"https://example.com/{i}") for i in range(5)]
        result = build_trending_alert(arts)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], dict)

    def test_respects_top_n(self):
        arts = [_article(f"Item {i}", url=f"https://example.com/{i}") for i in range(10)]
        result = build_trending_alert(arts, top_n=3)
        desc = result[0]["description"]
        assert "Item 0" in desc
        # Only top 3 shown
        assert desc.count("http") == 3

    def test_empty_articles_returns_placeholder(self):
        result = build_trending_alert([])
        desc = result[0]["description"]
        assert "No new" in desc or "no new" in desc.lower() or "_" in desc


class TestFormatPlainDigest:
    def test_returns_string(self):
        result = format_plain_digest(_report())
        assert isinstance(result, str)

    def test_contains_date(self):
        result = format_plain_digest(_report())
        assert "2026" in result

    def test_contains_article_titles(self):
        result = format_plain_digest(_report(n=2))
        assert "Article 0" in result
        assert "Article 1" in result

    def test_contains_counts(self):
        result = format_plain_digest(_report())
        assert "100" in result  # total_collected

    def test_all_sections_included(self):
        arts_a = [_article("A1", category=Category.TECH_NEWS)]
        arts_b = [_article("B1", category=Category.CYBERSECURITY)]
        sec_a = DigestSection(category=Category.TECH_NEWS, articles=arts_a)
        sec_b = DigestSection(category=Category.CYBERSECURITY, articles=arts_b)
        report = DigestReport(
            sections=[sec_a, sec_b],
            generated_at=datetime(2026, 7, 4, 8, 0, tzinfo=timezone.utc),
            total_collected=10,
            total_after_dedup=8,
            total_in_digest=2,
        )
        result = format_plain_digest(report)
        assert "A1" in result
        assert "B1" in result
