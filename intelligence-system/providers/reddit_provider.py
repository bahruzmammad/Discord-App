"""
Reddit public feed provider.

Uses Reddit's fully public JSON API — no authentication, no API key.
Only public .json endpoints are used (documented Reddit API).
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from models.article import Article, Category, utcnow
from providers.base import BaseProvider
from utils.http_client import fetch_json

import datetime


# ---------------------------------------------------------------------------
# Subreddit registry — (subreddit, category)
# ---------------------------------------------------------------------------
SUBREDDITS: List[Tuple[str, Category]] = [
    # Programming
    ("programming", Category.PROGRAMMING),
    ("Python", Category.PROGRAMMING),
    ("javascript", Category.PROGRAMMING),
    ("golang", Category.PROGRAMMING),
    ("rust", Category.PROGRAMMING),
    ("webdev", Category.PROGRAMMING),
    ("devops", Category.PROGRAMMING),
    ("MachineLearning", Category.CS_RESEARCH),
    ("learnmachinelearning", Category.CS_RESEARCH),
    ("artificial", Category.CS_RESEARCH),
    # CS Research
    ("compsci", Category.CS_RESEARCH),
    ("algorithms", Category.CS_RESEARCH),
    ("DistributedSystems", Category.CS_RESEARCH),
    # Cybersecurity
    ("netsec", Category.CYBERSECURITY),
    ("cybersecurity", Category.CYBERSECURITY),
    ("hacking", Category.CYBERSECURITY),  # educational only
    ("blackhat", Category.CYBERSECURITY),
    ("AskNetsec", Category.CYBERSECURITY),
    # Tech News
    ("technology", Category.TECH_NEWS),
    ("tech", Category.TECH_NEWS),
    ("science", Category.TECH_NEWS),
    # Open Source
    ("opensource", Category.OPEN_SOURCE),
    ("linux", Category.OPEN_SOURCE),
    ("selfhosted", Category.OPEN_SOURCE),
    # OSINT
    ("OSINT", Category.OSINT),
    ("privacy", Category.OSINT),
    ("digitalprivacy", Category.OSINT),
]

_MIN_SCORE = 10          # minimum upvotes to include
_MIN_RATIO = 0.6         # minimum upvote ratio to include
_MAX_AGE_HOURS = 48      # ignore posts older than 48 hours


def _is_recent(ts: float) -> bool:
    age_hours = (utcnow().timestamp() - ts) / 3600
    return age_hours <= _MAX_AGE_HOURS


class RedditProvider(BaseProvider):
    """Fetches top posts from curated public subreddits."""

    name = "reddit"

    async def _fetch_subreddit(self, subreddit: str, category: Category) -> List[Article]:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        data = await fetch_json(
            url,
            params={"limit": 25},
            user_agent=settings.collector.user_agent,
            timeout=settings.collector.http_timeout,
        )
        if not data:
            return []

        try:
            posts = data["data"]["children"]
        except (KeyError, TypeError):
            self.logger.warning("Unexpected Reddit JSON shape for r/%s", subreddit)
            return []

        articles: List[Article] = []
        for post in posts:
            p = post.get("data", {})
            if not p:
                continue

            # Filter
            score = p.get("score", 0)
            ratio = p.get("upvote_ratio", 0.0)
            created = p.get("created_utc", 0)
            is_self = p.get("is_self", False)
            stickied = p.get("stickied", False)
            nsfw = p.get("over_18", False)

            if stickied or nsfw:
                continue
            if score < _MIN_SCORE or ratio < _MIN_RATIO:
                continue
            if not _is_recent(created):
                continue

            title = (p.get("title") or "").strip()
            # Use external URL for link posts, Reddit URL for text posts
            if is_self:
                link_url = f"https://www.reddit.com{p.get('permalink', '')}"
            else:
                link_url = p.get("url", "")

            if not title or not link_url:
                continue

            # Build summary from selftext or link
            selftext = (p.get("selftext") or "")[:400].strip()
            summary = selftext if selftext and selftext not in ("[removed]", "[deleted]") else None

            ts = datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc)

            articles.append(
                Article(
                    title=title,
                    url=link_url,
                    source=f"r/{subreddit}",
                    category=category,
                    timestamp=ts,
                    summary=summary,
                    author=p.get("author"),
                    raw_score=float(score),
                    tags=[subreddit],
                    provider="reddit",
                )
            )

        return articles

    async def fetch(self) -> List[Article]:
        tasks = [
            asyncio.create_task(self._fetch_subreddit(sub, cat))
            for sub, cat in SUBREDDITS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles: List[Article] = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning("Subreddit fetch error: %s", result)
            else:
                all_articles.extend(result)
        return all_articles
