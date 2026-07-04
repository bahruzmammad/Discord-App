"""
Discord message formatter.

Converts DigestReport and Article objects into Discord-ready embed dicts
and plain text. Respects Discord's 2000-char message limit and 6000-char
embed limit by splitting long content into multiple embeds.

Writing style: clear, active voice, no em dashes, no cliches.
See config/style_rules.py for the full style guide.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from typing import List

from core.digest import DigestReport, DigestSection
from models.article import Article, Category

# Discord character limits
_EMBED_TITLE_MAX      = 256
_EMBED_DESC_MAX       = 4096
_EMBED_FIELD_NAME_MAX = 256
_EMBED_FIELD_VALUE_MAX = 1024
_EMBED_TOTAL_MAX      = 6000
_FIELDS_PER_EMBED     = 25
_MESSAGE_MAX          = 2000

# Sidebar colour per category
CATEGORY_COLOURS: dict[Category, int] = {
    Category.TECH_NEWS:     0x4A90D9,   # Blue
    Category.PROGRAMMING:   0x7ED321,   # Green
    Category.CS_RESEARCH:   0x9B59B6,   # Purple
    Category.CYBERSECURITY: 0xE74C3C,   # Red
    Category.OSINT:         0xF39C12,   # Orange
    Category.OPEN_SOURCE:   0x1ABC9C,   # Teal
    Category.UNKNOWN:       0x95A5A6,   # Grey
}


def _truncate(text: str, max_len: int, suffix: str = "...") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def _score_bar(score: float) -> str:
    filled = round(score * 5)
    return "▓" * filled + "░" * (5 - filled)


def _format_article_line(article: Article, idx: int) -> str:
    """Format one article as a numbered line for a Discord embed field."""
    title  = _truncate(article.title, 80)
    source = _truncate(article.source, 30)
    bar    = _score_bar(article.relevance_score)
    line   = f"{idx}. [{title}]({article.url})\n└ {source} · {bar}"
    if article.summary:
        snippet = _truncate(article.summary, 120)
        line += f"\n{snippet}"
    return line


def build_digest_header(report: DigestReport) -> dict:
    """Build the opening embed for a digest delivery."""
    date_str = report.generated_at.strftime("%A, %d %B %Y, %H:%M UTC")
    return {
        "title": "OSINT Intelligence Digest",
        "description": (
            f"{date_str}\n\n"
            f"Collected: {report.total_collected} articles. "
            f"After dedup: {report.total_after_dedup}. "
            f"In digest: {report.total_in_digest}."
        ),
        "color": 0x2C3E50,
        "footer": {"text": "OSINT Digest. Public data sources only."},
    }


def build_section_embeds(section: DigestSection) -> List[dict]:
    """
    Convert one DigestSection into one or more embed dicts.
    Sections with more than 8 articles are split across multiple embeds.
    """
    articles   = section.articles
    colour     = CATEGORY_COLOURS.get(section.category, 0x95A5A6)
    embeds: List[dict] = []
    chunk_size = 8

    for chunk_start in range(0, len(articles), chunk_size):
        chunk  = articles[chunk_start: chunk_start + chunk_size]
        fields = []
        for local_idx, article in enumerate(chunk):
            global_idx  = chunk_start + local_idx + 1
            field_value = _format_article_line(article, global_idx)
            field_value = _truncate(field_value, _EMBED_FIELD_VALUE_MAX)
            fields.append({
                "name":   "\u200b",
                "value":  field_value,
                "inline": False,
            })

        label = section.label + (" (continued)" if chunk_start > 0 else "")
        embeds.append({
            "title":  label,
            "color":  colour,
            "fields": fields,
            "footer": {"text": f"{len(articles)} articles in this category"},
        })

    return embeds


def build_digest_footer(report: DigestReport) -> dict:
    """Build the closing embed for a digest delivery."""
    return {
        "title": "End of Digest",
        "description": (
            f"Sources: RSS feeds, GitHub Trending, Reddit, "
            f"NVD/CISA CVEs, GitHub Security Advisories, news outlets.\n\n"
            f"All data from public sources. No API keys used."
        ),
        "color": 0x2C3E50,
    }


def build_trending_alert(articles: List[Article], top_n: int = 5) -> List[dict]:
    """Build a compact embed showing the top-N trending articles."""
    lines = []
    for i, article in enumerate(articles[:top_n], 1):
        emoji = Category.emoji(article.category)
        title = _truncate(article.title, 70)
        lines.append(f"{emoji} {i}. [{title}]({article.url})\n└ {article.source}")

    return [{
        "title":       "Trending Now: Intelligence Update",
        "description": "\n\n".join(lines) or "No new high-signal items.",
        "color":       0xF39C12,
        "footer":      {"text": f"Top {top_n} items. Updates run on schedule."},
    }]


def format_plain_digest(report: DigestReport) -> str:
    """
    Plain-text digest for DRY_RUN mode and stdout logging.
    No markdown, no special characters.
    """
    lines = [
        "=" * 60,
        "  OSINT INTELLIGENCE DIGEST",
        f"  {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 60,
        f"Collected: {report.total_collected}",
        f"After dedup: {report.total_after_dedup}",
        f"In digest: {report.total_in_digest}",
        "",
    ]

    for section in report.sections:
        lines.append(f"\n{'=' * 50}")
        lines.append(f"  {section.label}")
        lines.append(f"{'=' * 50}")
        for i, article in enumerate(section.articles, 1):
            lines.append(f"\n  {i}. {article.title}")
            lines.append(f"     Source: {article.source}")
            lines.append(f"     URL:    {article.url}")
            lines.append(f"     Score:  {article.relevance_score:.3f}")
            if article.summary:
                wrapped = textwrap.fill(
                    article.summary[:300],
                    width=70,
                    initial_indent="     ",
                    subsequent_indent="     ",
                )
                lines.append(wrapped)

    lines.append(f"\n{'=' * 60}\n")
    return "\n".join(lines)
