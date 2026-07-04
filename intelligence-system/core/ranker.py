"""
Ranking and scoring engine.

Computes a composite relevance_score (0.0–1.0) for each Article using:
- Recency decay: newer articles score higher
- Source credibility: curated multipliers per source domain
- Raw score normalisation: provider raw scores (upvotes, stars, CVSS)
- Keyword signal: high-value terms boost score
- Category weights: some categories are prioritised

The final score is normalised within each category to [0, 1].
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List

from models.article import Article, Category, utcnow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credibility multipliers by source domain keyword (substring match)
# ---------------------------------------------------------------------------
SOURCE_CREDIBILITY: Dict[str, float] = {
    # High credibility — primary sources
    "arxiv": 1.0,
    "nvd.nist": 1.0,
    "cisa.gov": 1.0,
    "github.com": 0.9,
    "github": 0.85,
    "ietf": 0.95,
    "ieee": 0.95,
    "acm.org": 0.95,
    "papers with code": 0.9,
    "distill.pub": 0.95,
    "hacker news": 0.85,
    "hn": 0.85,
    "krebs": 0.9,
    "schneier": 0.9,
    "bleepingcomputer": 0.85,
    "cert": 0.9,
    "linux foundation": 0.9,
    "rust blog": 0.9,
    "go blog": 0.9,
    # Good but slightly less authoritative
    "ars technica": 0.8,
    "wired": 0.8,
    "mit": 0.85,
    "techcrunch": 0.7,
    "the verge": 0.7,
    "reddit": 0.65,
    "dev.to": 0.65,
    "infoq": 0.75,
    "bbc": 0.85,
    "reuters": 0.85,
    "nytimes": 0.8,
    "guardian": 0.8,
    "ieee spectrum": 0.9,
    "stack overflow": 0.8,
    "netflix": 0.8,
    "meta engineering": 0.8,
    "aws": 0.75,
    "google cloud": 0.75,
    # Lower-signal
    "venturebeat": 0.6,
    "zdnet": 0.65,
    "cnet": 0.6,
}

# ---------------------------------------------------------------------------
# High-value keyword patterns (title / summary)
# ---------------------------------------------------------------------------
SIGNAL_KEYWORDS = re.compile(
    r"\b("
    r"critical|rce|remote code execution|zero.?day|0.?day|exploit|ransomware|"
    r"vulnerability|cve-|breach|attack|malware|backdoor|"
    r"llm|gpt|transformer|neural|diffusion|"
    r"distributed system|consensus|raft|paxos|"
    r"kubernetes|k8s|container|wasm|webassembly|"
    r"open.?source|release|launched|announces|new|update|"
    r"rust|golang|python 3|javascript|typescript|"
    r"ai safety|alignment|"
    r"quantum|breakthrough|research|paper|preprint"
    r")\b",
    re.IGNORECASE,
)

# Category base weights (determines cross-category ordering in digest)
CATEGORY_WEIGHTS: Dict[Category, float] = {
    Category.CYBERSECURITY: 1.0,    # highest priority — time-sensitive
    Category.TECH_NEWS: 0.9,
    Category.CS_RESEARCH: 0.88,
    Category.PROGRAMMING: 0.85,
    Category.OPEN_SOURCE: 0.8,
    Category.OSINT: 0.75,
    Category.UNKNOWN: 0.5,
}

# Recency decay half-life in hours (score halves every N hours)
_HALF_LIFE_HOURS = 24.0


def _recency_score(timestamp: datetime) -> float:
    """Exponential decay based on article age."""
    now = utcnow()
    age_hours = max(0.0, (now - timestamp).total_seconds() / 3600)
    return math.exp(-age_hours * math.log(2) / _HALF_LIFE_HOURS)


def _credibility_score(source: str) -> float:
    src_lower = source.lower()
    for keyword, score in SOURCE_CREDIBILITY.items():
        if keyword in src_lower:
            return score
    return 0.55  # unknown source baseline


def _keyword_boost(article: Article) -> float:
    """Returns a boost in [0, 0.3] based on high-signal keyword matches."""
    text = f"{article.title} {article.summary or ''}"
    matches = len(SIGNAL_KEYWORDS.findall(text))
    return min(0.3, matches * 0.05)


def _normalise_raw(articles_in_category: List[Article]) -> Dict[str, float]:
    """Map raw_score to [0, 1] within a category."""
    if not articles_in_category:
        return {}
    scores = [a.raw_score for a in articles_in_category]
    max_score = max(scores) if scores else 1.0
    if max_score == 0:
        return {a.content_id: 0.0 for a in articles_in_category}
    return {a.content_id: a.raw_score / max_score for a in articles_in_category}


class Ranker:
    """Assigns relevance_score to each Article in-place."""

    def rank(self, articles: List[Article]) -> List[Article]:
        if not articles:
            return articles

        # Normalise raw scores within each category
        by_category: Dict[Category, List[Article]] = {}
        for a in articles:
            by_category.setdefault(a.category, []).append(a)

        norm_maps: Dict[Category, Dict[str, float]] = {}
        for cat, cat_articles in by_category.items():
            norm_maps[cat] = _normalise_raw(cat_articles)

        # Compute composite score
        for article in articles:
            recency = _recency_score(article.timestamp)
            credibility = _credibility_score(article.source)
            raw_norm = norm_maps.get(article.category, {}).get(article.content_id, 0.0)
            keyword = _keyword_boost(article)
            cat_weight = CATEGORY_WEIGHTS.get(article.category, 0.5)

            # Weighted composite
            score = (
                recency * 0.30
                + credibility * 0.25
                + raw_norm * 0.20
                + keyword * 0.15
                + (cat_weight - 0.5) * 0.10  # normalise cat weight contribution
            )
            article.relevance_score = round(min(1.0, max(0.0, score)), 4)

        articles.sort(key=lambda a: a.relevance_score, reverse=True)
        logger.info("Ranked %d articles (top score: %.3f)", len(articles),
                    articles[0].relevance_score if articles else 0)
        return articles
