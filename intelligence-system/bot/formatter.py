"""
Discord message formatter.

Converts DigestReport and Article objects into Discord-ready strings
and discord.py Embed objects. Respects Discord's 2000-char message limit
and 6000-char embed limit by splitting content into multiple messages/embeds.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from core.digest import DigestReport, DigestSection
from models.article import Article, Category

# Discord limits
_EMBED_TITLE_MAX = 256
_EMBED_DESC_MAX = 4096
_EMBED_FIELD_NAME_MAX = 256
_EMBED_FIELD_VALUE_MAX = 1024
_EMBED_TOTAL_MAX = 6000
_FIELDS_PER_EMBED = 25
_MESSAGE_MAX = 2000

# Colour palette per category (Discord sidebar colour as int)
CATEGORY_COLOURS: dict[Category, int] = {
    Category.TECH_NEWS: 0x4A90D9,      # Blue
    Category.PROGRAMMING: 0x7ED321,    # Green
    Category.CS_RESEARCH: 0x9B59B6,    # Purple
    Category.CYBERSECURITY: 0xE74C3C,  # Red
    Category.OSINT: 0xF39C12,          # Orange
    Category.OPEN_SOURCE: 0x1ABC9C,    # Teal
    Category.UNKNOWN: 0x95A5A6,        # Grey
}


def _truncate(text: str, max_len: int, suffix: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def _format_article_line(article: Article, idx: int) -> str:
    """Single article line for use inside an embed field value."""
    score_bar = "▓" * round(article.relevance_score * 5) + "░" * (5 - round(article.relevance_score * 5))
    title = _truncate(article.title, 80)
    source = _truncate(article.source, 30)
    line = f"**{idx}.** [{title}]({article.url})\n└ `{source}` · `{score_bar}`"
    if article.summary:
        snippet = _truncate(article.summary, 120)
        line += f"\n*{snippet}*"
    return line


def build_digest_header(report: DigestReport) -> dict:
    """Returns kwargs for a discord.py Embed (the digest header card)."""
    date_str = report.generated_at.strftime("%A, %d %B %Y · %H:%M UTC")
    return {
        "title": "🛰️ OSINT Intelligence Digest",
        "description": (
            f"**{date_str}**\n\n"
            f"> *One system. One feed. Zero noise.*\n\n"
            f"📥 **{report.total_collected}** collected  "
            f"→  🔍 **{report.total_after_dedup}** after dedup  "
            f"→  📋 **{report.total_in_digest}** in digest"
        ),
        "color": 0x2C3E50,
        "footer": {"text": "OSINT Digest · github.com/your-org/osint-digest · Powered by public data only"},
    }


def build_section_embeds(section: DigestSection) -> List[dict]:
    """
    Convert one DigestSection into one or more embed dicts.
    Splits if the section has > 10 articles (embed field limit).
    """
    articles = section.articles
    colour = CATEGORY_COLOURS.get(section.category, 0x95A5A6)
    embeds: List[dict] = []

    # Split into chunks of 8 articles per embed
    chunk_size = 8
    for chunk_start in range(0, len(articles), chunk_size):
        chunk = articles[chunk_start: chunk_start + chunk_size]
        fields = []
        for local_idx, article in enumerate(chunk):
            global_idx = chunk_start + local_idx + 1
            field_value = _format_article_line(article, global_idx)
            # Ensure field value fits
            field_value = _truncate(field_value, _EMBED_FIELD_VALUE_MAX)
            fields.append({"name": "\u200b", "value": field_value, "inline": False})

        chunk_label = f" (cont.)" if chunk_start > 0 else ""
        embeds.append({
            "title": f"{section.label}{chunk_label}",
            "color": colour,
            "fields": fields,
            "footer": {"text": f"{len(articles)} articles in this category"},
        })

    return embeds


def build_digest_footer(report: DigestReport) -> dict:
    """Closing embed with metadata and next-run hint."""
    return {
        "title": "📊 End of Intelligence Digest",
        "description": (
            "─" * 36 + "\n"
            f"Next digest will be delivered at the scheduled time.\n\n"
            f"**Data sources:** RSS feeds · GitHub Trending · Reddit public · "
            f"NVD/CISA CVEs · GitHub Security Advisories · News outlets\n\n"
            f"*All data collected from legally public sources only.*"
        ),
        "color": 0x2C3E50,
    }


def build_trending_alert(articles: List[Article], top_n: int = 5) -> List[dict]:
    """
    Build a compact trending-alert embed for periodic updates.
    Shows the top-N articles across all categories.
    """
    lines = []
    for i, article in enumerate(articles[:top_n], 1):
        emoji = Category.emoji(article.category)
        title = _truncate(article.title, 70)
        lines.append(f"{emoji} **{i}.** [{title}]({article.url})\n└ `{article.source}`")

    return [{
        "title": "⚡ Trending Now — Intelligence Update",
        "description": "\n\n".join(lines) or "_No new high-signal items._",
        "color": 0xF39C12,
        "footer": {"text": f"Top {top_n} trending items · Updated every few hours"},
    }]


def format_plain_digest(report: DigestReport) -> str:
    """
    Plain-text version of the digest (for DRY_RUN logging or non-Discord output).
    """
    lines = [
        "=" * 60,
        f"  OSINT INTELLIGENCE DIGEST",
        f"  {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 60,
        f"Collected: {report.total_collected}  |  "
        f"After dedup: {report.total_after_dedup}  |  "
        f"In digest: {report.total_in_digest}",
        "",
    ]
    for section in report.sections:
        lines.append(f"\n{'─' * 50}")
        lines.append(f"  {section.label}")
        lines.append(f"{'─' * 50}")
        for i, article in enumerate(section.articles, 1):
            lines.append(f"\n  {i}. {article.title}")
            lines.append(f"     Source : {article.source}")
            lines.append(f"     URL    : {article.url}")
            lines.append(f"     Score  : {article.relevance_score:.3f}")
            if article.summary:
                wrapped = textwrap.fill(article.summary[:300], width=70,
                                        initial_indent="     ", subsequent_indent="     ")
                lines.append(wrapped)

    lines.append(f"\n{'=' * 60}\n")
    return "\n".join(lines)
