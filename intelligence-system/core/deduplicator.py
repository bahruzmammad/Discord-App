"""
Deduplication engine.

Two-pass deduplication:
1. Exact URL fingerprint — removes identical URLs immediately.
2. Fuzzy title similarity — removes near-duplicate titles using
   token overlap (Jaccard similarity), no external ML dependencies needed.
"""

from __future__ import annotations

import logging
import re
from typing import List, Set

from models.article import Article

logger = logging.getLogger(__name__)


def _tokenise(text: str) -> Set[str]:
    """Lowercase alphanumeric tokens, min 3 chars."""
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


class Deduplicator:
    """
    Removes duplicate Articles from a list.

    Args:
        threshold: Jaccard similarity above which two articles are
                   considered duplicates (default 0.75).
    """

    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold

    def deduplicate(self, articles: List[Article]) -> List[Article]:
        """
        Return a deduplicated list, keeping the highest raw_score copy
        when two articles are identical/similar.
        """
        if not articles:
            return articles

        before = len(articles)

        # Pass 1: exact URL dedup
        url_seen: dict[str, Article] = {}
        for article in articles:
            fid = article.content_id
            if fid not in url_seen or article.raw_score > url_seen[fid].raw_score:
                url_seen[fid] = article

        candidates = list(url_seen.values())

        # Pass 2: fuzzy title dedup (O(n²) but n is small — typically < 1000)
        # Build token sets for all candidates up front
        token_cache = {a.content_id: _tokenise(a.title_fingerprint) for a in candidates}

        # Cluster similar titles together, then keep the highest-scoring member
        cluster_map: dict[str, str] = {}  # content_id → canonical content_id (highest scorer)

        for i, article in enumerate(candidates):
            cid_i = article.content_id
            if cid_i not in cluster_map:
                cluster_map[cid_i] = cid_i  # start as its own canonical
            tok_i = token_cache[cid_i]
            canonical_i = cluster_map[cid_i]

            for j in range(i + 1, len(candidates)):
                other = candidates[j]
                cid_j = other.content_id
                if cluster_map.get(cid_j, cid_j) == cluster_map.get(cid_i, cid_i):
                    continue  # already same cluster
                tok_j = token_cache[cid_j]
                if _jaccard(tok_i, tok_j) >= self.threshold:
                    # Merge j's cluster into i's; canonical = highest raw_score
                    cid_j_canonical = cluster_map.get(cid_j, cid_j)
                    cid_i_canonical = cluster_map.get(cid_i, cid_i)
                    canonical_i_article = next(a for a in candidates if a.content_id == cid_i_canonical)
                    canonical_j_article = next(a for a in candidates if a.content_id == cid_j_canonical)
                    winner = cid_i_canonical if canonical_i_article.raw_score >= canonical_j_article.raw_score else cid_j_canonical
                    # Point all members of both clusters to the winner
                    for cid, can in list(cluster_map.items()):
                        if can in (cid_i_canonical, cid_j_canonical):
                            cluster_map[cid] = winner
                    cluster_map[cid_j] = winner
                    cluster_map[cid_i] = winner

        # Build unique list: one article per canonical ID, preserving order
        seen_canonicals: Set[str] = set()
        unique: List[Article] = []
        # Index by content_id for O(1) lookup
        id_to_article: dict[str, Article] = {a.content_id: a for a in candidates}
        for article in candidates:
            canonical = cluster_map.get(article.content_id, article.content_id)
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                unique.append(id_to_article[canonical])

        after = len(unique)
        logger.info("Deduplication: %d → %d items (removed %d)", before, after, before - after)
        return unique
