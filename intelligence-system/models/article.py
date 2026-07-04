"""
Unified data model for all collected intelligence items.
Every provider normalizes its output to this schema.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class Category(str, Enum):
    TECH_NEWS = "tech_news"
    PROGRAMMING = "programming"
    CS_RESEARCH = "cs_research"
    CYBERSECURITY = "cybersecurity"
    OSINT = "osint"
    OPEN_SOURCE = "open_source"
    UNKNOWN = "unknown"

    @classmethod
    def label(cls, value: "Category") -> str:
        labels = {
            cls.TECH_NEWS: "🌐 Global Tech & News",
            cls.PROGRAMMING: "💻 Programming & Dev",
            cls.CS_RESEARCH: "🔬 CS Research",
            cls.CYBERSECURITY: "🔒 Cybersecurity",
            cls.OSINT: "🕵️ OSINT & Intelligence",
            cls.OPEN_SOURCE: "📦 Open Source",
            cls.UNKNOWN: "📰 Other",
        }
        return labels.get(value, "📰 Other")

    @classmethod
    def emoji(cls, value: "Category") -> str:
        return cls.label(value).split()[0]


@dataclass
class Article:
    """Normalised intelligence item. Every field is required after construction."""

    title: str
    url: str
    source: str
    category: Category
    timestamp: datetime
    summary: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    relevance_score: float = 0.0          # 0.0 – 1.0, set by ranker
    cluster_id: Optional[int] = None      # set by clusterer
    # Provider-assigned raw score (e.g. GitHub stars, Reddit score)
    raw_score: float = 0.0
    provider: str = ""

    # ------------------------------------------------------------------ #
    # Derived helpers                                                      #
    # ------------------------------------------------------------------ #

    @property
    def content_id(self) -> str:
        """Stable fingerprint based on URL (used for deduplication)."""
        return hashlib.sha256(self._normalise_url(self.url).encode()).hexdigest()[:16]

    @property
    def title_fingerprint(self) -> str:
        """Normalised title for fuzzy deduplication."""
        return re.sub(r"[^a-z0-9 ]", "", self.title.lower()).strip()

    @staticmethod
    def _normalise_url(url: str) -> str:
        """Strip UTM params and trailing slashes for stable hashing."""
        url = re.sub(r"[?&](utm_[^&]+)", "", url)
        return url.rstrip("/").lower()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "author": self.author,
            "tags": self.tags,
            "relevance_score": round(self.relevance_score, 4),
            "raw_score": self.raw_score,
            "provider": self.provider,
            "cluster_id": self.cluster_id,
        }

    def __repr__(self) -> str:
        return (
            f"<Article [{self.category.value}] score={self.relevance_score:.2f} "
            f'"{self.title[:60]}">'
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
