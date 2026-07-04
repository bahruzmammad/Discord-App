"""
GitHub Trending provider.

Uses the unofficial GitHub trending page (HTML scraping) and the
official public GitHub API (no auth required for basic endpoints).
No API token is needed.
"""

from __future__ import annotations

import asyncio
import re
from typing import List

from config.settings import settings
from models.article import Article, Category, utcnow
from providers.base import BaseProvider
from utils.http_client import fetch_json, fetch_text


class GitHubTrendingProvider(BaseProvider):
    """Collects trending repositories from GitHub."""

    name = "github"

    # Languages to pull trending repos for
    _LANGUAGES = ["", "python", "javascript", "go", "rust", "typescript", "java", "c"]
    _PERIODS = ["daily", "weekly"]
    _BASE = "https://github.com/trending"

    async def _fetch_trending_html(self, lang: str, period: str) -> List[Article]:
        url = f"{self._BASE}/{lang}?since={period}" if lang else f"{self._BASE}?since={period}"
        html = await fetch_text(url, user_agent=settings.collector.user_agent, timeout=settings.collector.http_timeout)
        if not html:
            return []

        articles: List[Article] = []
        # Parse repository blocks from GitHub's HTML
        # Pattern: /owner/repo links inside article tags
        repo_pattern = re.compile(
            r'href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"[^>]*>\s*<h[12][^>]*>\s*(?:<span[^>]*>.*?</span>\s*)?'
            r'([a-zA-Z0-9_.-]+)\s*/\s*([a-zA-Z0-9_.-]+)',
            re.DOTALL,
        )
        desc_pattern = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', re.DOTALL)
        star_pattern = re.compile(r'<span[^>]*class="[^"]*d-inline-block[^"]*float-sm-right[^"]*"[^>]*>.*?'
                                   r'([\d,]+)\s*stars\s*today', re.DOTALL)

        seen_repos = set()
        # Simpler extraction: find all /owner/repo href patterns
        all_repos = re.findall(r'href="/([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)"', html)
        descriptions = re.findall(r'<p[^>]*>\s*([^<]{20,300}?)\s*</p>', html)
        stars_today = re.findall(r'([\d,]+)\s+stars?\s+today', html)

        desc_idx = 0
        stars_idx = 0

        for repo_path in all_repos:
            parts = repo_path.strip("/").split("/")
            if len(parts) != 2:
                continue
            if repo_path in seen_repos:
                continue
            # Filter out GitHub navigation paths
            owner, repo = parts
            if owner in ("login", "join", "organizations", "explore", "trending", "topics",
                         "collections", "events", "marketplace", "sponsors", "features",
                         "about", "contact", "pricing", "security", "blog", "readme"):
                continue
            seen_repos.add(repo_path)

            summary = descriptions[desc_idx].strip() if desc_idx < len(descriptions) else None
            stars_raw = stars_today[stars_idx].replace(",", "") if stars_idx < len(stars_today) else "0"
            try:
                raw_score = float(stars_raw)
            except ValueError:
                raw_score = 0.0

            desc_idx += 1
            stars_idx += 1

            lang_label = f" [{lang.capitalize()}]" if lang else ""
            articles.append(
                Article(
                    title=f"{repo_path}{lang_label}",
                    url=f"https://github.com/{repo_path}",
                    source="GitHub Trending",
                    category=Category.OPEN_SOURCE,
                    timestamp=utcnow(),
                    summary=summary[:300] if summary else None,
                    raw_score=raw_score,
                    tags=[lang] if lang else [],
                    provider="github",
                )
            )

            if len(articles) >= 25:
                break

        return articles

    async def _fetch_search_repos(self) -> List[Article]:
        """Supplement with GitHub's public search API — no auth needed."""
        articles: List[Article] = []
        queries = [
            ("stars:>500 created:>2024-01-01 topic:machine-learning", Category.CS_RESEARCH),
            ("stars:>200 created:>2024-01-01 topic:security", Category.CYBERSECURITY),
            ("stars:>300 pushed:>2024-01-01 topic:devops", Category.PROGRAMMING),
        ]
        for q, cat in queries:
            data = await fetch_json(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": 10},
                user_agent="OSINTDigestBot/1.0",
                timeout=settings.collector.http_timeout,
            )
            if not data or "items" not in data:
                continue
            for item in data["items"][:10]:
                articles.append(
                    Article(
                        title=item.get("full_name", ""),
                        url=item.get("html_url", ""),
                        source="GitHub Search",
                        category=cat,
                        timestamp=utcnow(),
                        summary=item.get("description", None),
                        raw_score=float(item.get("stargazers_count", 0)),
                        tags=([item["language"]] if item.get("language") else []),
                        provider="github",
                    )
                )
        return articles

    async def fetch(self) -> List[Article]:
        tasks: List = []
        # Only fetch daily trending for the main page + top languages
        for lang in self._LANGUAGES[:5]:
            tasks.append(asyncio.create_task(self._fetch_trending_html(lang, "daily")))
        tasks.append(asyncio.create_task(self._fetch_search_repos()))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: List[Article] = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.warning("GitHub fetch error: %s", r)
            else:
                articles.extend(r)

        # Deduplicate by URL within this provider
        seen: set = set()
        unique: List[Article] = []
        for a in articles:
            if a.url not in seen:
                seen.add(a.url)
                unique.append(a)

        return unique[: settings.collector.max_items_per_provider * 2]
