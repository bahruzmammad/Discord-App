"""
News provider — uses public NewsAPI-compatible endpoints and additional
curated RSS feeds for global tech and science news.

Falls back gracefully if any source is unreachable.
No API key is required for the RSS-only sources.
Optional: set NEWS_API_KEY for the newsapi.org source.
"""

from __future__ import annotations

import asyncio
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

from config.settings import settings
from models.article import Article, Category, utcnow
from providers.base import BaseProvider
from utils.http_client import fetch_json, fetch_text


def _parse_date(raw: Optional[str]) -> datetime:
    if not raw:
        return utcnow()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:25], fmt)
            return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt
        except Exception:
            continue
    return utcnow()


def _strip_tags(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()[:500]


# RSS feeds exclusively for news (no API key needed)
NEWS_RSS_FEEDS: List[Tuple[str, Category, str]] = [
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", Category.TECH_NEWS, "BBC Tech"),
    ("https://rss.cnn.com/rss/edition_technology.rss", Category.TECH_NEWS, "CNN Tech"),
    ("https://www.theguardian.com/technology/rss", Category.TECH_NEWS, "The Guardian Tech"),
    ("https://feeds.nbcnews.com/nbcnews/public/tech", Category.TECH_NEWS, "NBC Tech"),
    ("https://www.sciencedaily.com/rss/computers_math/computer_science.xml", Category.CS_RESEARCH, "ScienceDaily CS"),
    ("https://phys.org/rss-feed/technology-news/", Category.TECH_NEWS, "Phys.org"),
    ("https://venturebeat.com/feed/", Category.TECH_NEWS, "VentureBeat"),
    ("https://gigaom.com/feed/", Category.TECH_NEWS, "GigaOm"),
    ("https://readwrite.com/feed/", Category.TECH_NEWS, "ReadWrite"),
    ("https://spectrum.ieee.org/rss", Category.CS_RESEARCH, "IEEE Spectrum"),
    ("https://www.zdnet.com/news/rss.xml", Category.TECH_NEWS, "ZDNet"),
    ("https://www.cnet.com/rss/news/", Category.TECH_NEWS, "CNET"),
    ("https://feeds.macrumors.com/MacRumors-All", Category.TECH_NEWS, "MacRumors"),
    ("https://9to5google.com/feed/", Category.TECH_NEWS, "9to5Google"),
    ("https://9to5mac.com/feed/", Category.TECH_NEWS, "9to5Mac"),
]


def _parse_rss_feed(text: str, category: Category, source: str) -> List[Article]:
    articles: List[Article] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return articles

    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")

    for item in items[:20]:
        title_el = item.find("title")
        link_el = item.find("link")
        date_el = item.find("pubDate")
        desc_el = item.find("description")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""
        date_raw = (date_el.text or "") if date_el is not None else ""
        summary = _strip_tags((desc_el.text or "") if desc_el is not None else "")

        if not title or not url:
            continue

        articles.append(
            Article(
                title=title,
                url=url,
                source=source,
                category=category,
                timestamp=_parse_date(date_raw),
                summary=summary or None,
                provider="news",
            )
        )

    return articles


class NewsProvider(BaseProvider):
    """Aggregates technology and science news from public RSS feeds."""

    name = "news"

    async def _fetch_rss(self, url: str, category: Category, source: str) -> List[Article]:
        text = await fetch_text(
            url,
            user_agent=settings.collector.user_agent,
            timeout=settings.collector.http_timeout,
        )
        if not text:
            return []
        return _parse_rss_feed(text, category, source)

    async def _fetch_newsapi(self) -> List[Article]:
        """Optional NewsAPI.org source — only runs if NEWS_API_KEY is set."""
        api_key = os.environ.get("NEWS_API_KEY", "").strip()
        if not api_key:
            return []

        data = await fetch_json(
            "https://newsapi.org/v2/top-headlines",
            params={
                "category": "technology",
                "language": "en",
                "pageSize": 20,
                "apiKey": api_key,
            },
            user_agent=settings.collector.user_agent,
            timeout=settings.collector.http_timeout,
        )
        if not data or data.get("status") != "ok":
            return []

        articles: List[Article] = []
        for item in data.get("articles", []):
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url or title == "[Removed]":
                continue
            articles.append(
                Article(
                    title=title,
                    url=url,
                    source=item.get("source", {}).get("name", "NewsAPI"),
                    category=Category.TECH_NEWS,
                    timestamp=_parse_date(item.get("publishedAt")),
                    summary=(item.get("description") or "")[:400] or None,
                    provider="news",
                )
            )

        return articles

    async def fetch(self) -> List[Article]:
        tasks = [
            asyncio.create_task(self._fetch_rss(url, cat, src))
            for url, cat, src in NEWS_RSS_FEEDS
        ]
        tasks.append(asyncio.create_task(self._fetch_newsapi()))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: List[Article] = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.warning("News fetch error: %s", r)
            else:
                articles.extend(r)

        return articles
