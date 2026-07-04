"""
RSS / Atom feed provider.

Fetches a curated set of public RSS feeds covering technology, programming,
computer science, cybersecurity, and open-source — plus any user-supplied
extra feeds from the EXTRA_RSS_FEEDS environment variable.
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from config.settings import settings
from models.article import Article, Category, utcnow
from providers.base import BaseProvider
from utils.http_client import fetch_text

# ---------------------------------------------------------------------------
# Feed registry — (url, category, source_label)
# ---------------------------------------------------------------------------
FEEDS: List[Tuple[str, Category, str]] = [
    # ── Tech News ──────────────────────────────────────────────────────────
    ("https://feeds.feedburner.com/TechCrunch", Category.TECH_NEWS, "TechCrunch"),
    ("https://www.wired.com/feed/rss", Category.TECH_NEWS, "Wired"),
    ("https://arstechnica.com/feed/", Category.TECH_NEWS, "Ars Technica"),
    ("https://www.theverge.com/rss/index.xml", Category.TECH_NEWS, "The Verge"),
    ("https://feeds.reuters.com/reuters/technologyNews", Category.TECH_NEWS, "Reuters Tech"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", Category.TECH_NEWS, "NYT Tech"),
    ("https://www.technologyreview.com/feed/", Category.TECH_NEWS, "MIT Tech Review"),
    # ── Programming & Dev ──────────────────────────────────────────────────
    ("https://feeds.feedburner.com/hmarkets", Category.PROGRAMMING, "Hacker News"),
    ("https://hnrss.org/frontpage", Category.PROGRAMMING, "Hacker News"),
    ("https://dev.to/feed", Category.PROGRAMMING, "dev.to"),
    ("https://www.infoq.com/feed/", Category.PROGRAMMING, "InfoQ"),
    ("https://blog.golang.org/feed.atom", Category.PROGRAMMING, "Go Blog"),
    ("https://blog.rust-lang.org/feed.xml", Category.PROGRAMMING, "Rust Blog"),
    ("https://pypi.org/rss/updates.xml", Category.PROGRAMMING, "PyPI Updates"),
    ("https://www.python.org/jobs/feed/rss/", Category.PROGRAMMING, "Python.org"),
    ("https://stackoverflow.blog/feed/", Category.PROGRAMMING, "Stack Overflow Blog"),
    ("https://engineering.fb.com/feed/", Category.PROGRAMMING, "Meta Engineering"),
    ("https://netflixtechblog.com/feed", Category.PROGRAMMING, "Netflix Tech Blog"),
    ("https://aws.amazon.com/blogs/aws/feed/", Category.PROGRAMMING, "AWS Blog"),
    ("https://cloud.google.com/blog/rss/", Category.PROGRAMMING, "Google Cloud Blog"),
    ("https://devblogs.microsoft.com/dotnet/feed/", Category.PROGRAMMING, "Microsoft .NET Blog"),
    # ── CS Research ────────────────────────────────────────────────────────
    ("https://arxiv.org/rss/cs.AI", Category.CS_RESEARCH, "arXiv cs.AI"),
    ("https://arxiv.org/rss/cs.DS", Category.CS_RESEARCH, "arXiv cs.DS"),
    ("https://arxiv.org/rss/cs.DC", Category.CS_RESEARCH, "arXiv cs.DC"),
    ("https://arxiv.org/rss/cs.NI", Category.CS_RESEARCH, "arXiv cs.NI"),
    ("https://arxiv.org/rss/cs.CR", Category.CS_RESEARCH, "arXiv cs.CR"),
    ("https://paperswithcode.com/latest.rss", Category.CS_RESEARCH, "Papers With Code"),
    ("https://distill.pub/rss.xml", Category.CS_RESEARCH, "Distill.pub"),
    # ── Cybersecurity ──────────────────────────────────────────────────────
    ("https://feeds.feedburner.com/TheHackersNews", Category.CYBERSECURITY, "The Hacker News"),
    ("https://www.bleepingcomputer.com/feed/", Category.CYBERSECURITY, "BleepingComputer"),
    ("https://krebsonsecurity.com/feed/", Category.CYBERSECURITY, "Krebs on Security"),
    ("https://www.darkreading.com/rss.xml", Category.CYBERSECURITY, "Dark Reading"),
    ("https://www.schneier.com/blog/atom.xml", Category.CYBERSECURITY, "Schneier on Security"),
    ("https://www.cisa.gov/uscert/ncas/alerts.xml", Category.CYBERSECURITY, "CISA Alerts"),
    ("https://www.cert.org/vince/public/list/", Category.CYBERSECURITY, "CERT/CC"),
    ("https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml", Category.CYBERSECURITY, "NVD CVE"),
    ("https://www.us-cert.gov/ncas/current-activity.xml", Category.CYBERSECURITY, "US-CERT"),
    # ── OSINT & Policy ─────────────────────────────────────────────────────
    ("https://www.eff.org/rss/updates.xml", Category.OSINT, "EFF"),
    ("https://www.accessnow.org/feed/", Category.OSINT, "Access Now"),
    ("https://www.techpolicy.press/feed/", Category.OSINT, "Tech Policy Press"),
    # ── Open Source ────────────────────────────────────────────────────────
    ("https://opensource.com/feed", Category.OPEN_SOURCE, "Opensource.com"),
    ("https://lwn.net/headlines/rss", Category.OPEN_SOURCE, "LWN.net"),
    ("https://linuxfoundation.org/feed/", Category.OPEN_SOURCE, "Linux Foundation"),
]

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def _strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:500]


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
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return utcnow()


def _parse_feed_xml(xml_text: str, category: Category, source: str) -> List[Article]:
    """Parse RSS 2.0 or Atom 1.0 XML into Article objects."""
    articles: List[Article] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    # Determine feed type
    tag = root.tag
    is_atom = "atom" in tag or "feed" in tag.lower()

    if is_atom:
        items = root.findall("atom:entry", _NS) or root.findall("entry")
    else:
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

    for item in items:
        if is_atom:
            title_el = item.find("atom:title", _NS) or item.find("title")
            link_el = item.find("atom:link[@rel='alternate']", _NS) or item.find("atom:link", _NS) or item.find("link")
            date_el = item.find("atom:updated", _NS) or item.find("atom:published", _NS) or item.find("updated") or item.find("published")
            summary_el = item.find("atom:summary", _NS) or item.find("atom:content", _NS) or item.find("summary") or item.find("content")
            author_el = item.find("atom:author/atom:name", _NS) or item.find("author/name")

            title = (title_el.text or "").strip() if title_el is not None else ""
            url = link_el.get("href", "") if link_el is not None else ""
            if not url and link_el is not None:
                url = (link_el.text or "").strip()
            date_raw = (date_el.text or "") if date_el is not None else ""
            summary = _strip_html((summary_el.text or "") if summary_el is not None else "")
            author = (author_el.text or "").strip() if author_el is not None else None
        else:
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate") or item.find("dc:date", _NS)
            summary_el = item.find("description") or item.find("content:encoded", _NS)
            author_el = item.find("dc:creator", _NS) or item.find("author")

            title = (title_el.text or "").strip() if title_el is not None else ""
            url = (link_el.text or "").strip() if link_el is not None else ""
            date_raw = (date_el.text or "") if date_el is not None else ""
            summary = _strip_html((summary_el.text or "") if summary_el is not None else "")
            author = (author_el.text or "").strip() if author_el is not None else None

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
                author=author or None,
                provider="rss",
            )
        )

    return articles


class RSSProvider(BaseProvider):
    """Fetches all RSS / Atom feeds concurrently."""

    name = "rss"

    def __init__(self, extra_feeds: Optional[List[Tuple[str, Category, str]]] = None) -> None:
        super().__init__()
        self._feeds = list(FEEDS)
        if extra_feeds:
            self._feeds.extend(extra_feeds)
        # Add extra feeds from environment
        for url in settings.collector.extra_rss_feeds:
            self._feeds.append((url, Category.TECH_NEWS, urlparse(url).netloc or url))

    async def _fetch_one(self, url: str, category: Category, source: str) -> List[Article]:
        text = await fetch_text(
            url,
            user_agent=settings.collector.user_agent,
            timeout=settings.collector.http_timeout,
        )
        if not text:
            self.logger.debug("Empty response from %s", url)
            return []
        articles = _parse_feed_xml(text, category, source)
        return articles[: settings.collector.max_items_per_provider]

    async def fetch(self) -> List[Article]:
        tasks = [
            asyncio.create_task(self._fetch_one(url, cat, src))
            for url, cat, src in self._feeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles: List[Article] = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning("Feed error: %s", result)
            else:
                all_articles.extend(result)
        return all_articles
