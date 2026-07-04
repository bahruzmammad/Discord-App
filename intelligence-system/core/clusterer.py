"""
Topic clustering engine.

Groups articles about the same story/topic into clusters using a
lightweight TF-IDF bag-of-words approach + greedy single-linkage
clustering. No ML dependencies required.

Each Article gets a cluster_id assigned in-place. The cluster with
the highest average relevance_score is cluster 0.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from models.article import Article

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    "a an the and or not but is are was were be been being have has had do does did "
    "will would shall should may might must can could to of in on at by for with as "
    "from this that these those it its it's we they their our your he she him her his "
    "then than also just been only up out if so about after before over under between "
    "into through during while because both each all any more some such no nor very".split()
)


def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    tf: Dict[str, float] = defaultdict(float)
    for t in tokens:
        tf[t] += 1.0
    n = len(tokens) or 1
    return {t: (count / n) * idf.get(t, 1.0) for t, count in tf.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    dot = sum(a.get(t, 0.0) * b.get(t, 0.0) for t in b)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if not mag_a or not mag_b:
        return 0.0
    return dot / (mag_a * mag_b)


class Clusterer:
    """
    Groups articles into topic clusters.

    Args:
        threshold: Cosine similarity above which two articles are
                   placed in the same cluster (default 0.30).
    """

    def __init__(self, threshold: float = 0.30) -> None:
        self.threshold = threshold

    def cluster(self, articles: List[Article]) -> List[Article]:
        if len(articles) < 2:
            for i, a in enumerate(articles):
                a.cluster_id = i
            return articles

        # Build IDF
        all_tokens = [_tokens(f"{a.title} {a.summary or ''}") for a in articles]
        df: Dict[str, int] = defaultdict(int)
        N = len(articles)
        for tokens in all_tokens:
            for t in set(tokens):
                df[t] += 1
        idf = {t: math.log((N + 1) / (count + 1)) + 1.0 for t, count in df.items()}

        # Build TF-IDF vectors
        vectors = [_tfidf_vector(tokens, idf) for tokens in all_tokens]

        # Greedy single-linkage clustering
        cluster_ids: List[Optional[int]] = [None] * N
        next_cluster = 0

        for i in range(N):
            if cluster_ids[i] is not None:
                continue
            cluster_ids[i] = next_cluster
            for j in range(i + 1, N):
                if cluster_ids[j] is not None:
                    continue
                sim = _cosine(vectors[i], vectors[j])
                if sim >= self.threshold:
                    cluster_ids[j] = next_cluster
            next_cluster += 1

        # Assign cluster IDs to articles
        for article, cid in zip(articles, cluster_ids):
            article.cluster_id = cid

        # Re-number clusters by average relevance (cluster 0 = most relevant)
        cluster_scores: Dict[int, List[float]] = defaultdict(list)
        for article in articles:
            if article.cluster_id is not None:
                cluster_scores[article.cluster_id].append(article.relevance_score)

        ranked_clusters = sorted(
            cluster_scores.keys(),
            key=lambda cid: sum(cluster_scores[cid]) / len(cluster_scores[cid]),
            reverse=True,
        )
        remap: Dict[int, int] = {old: new for new, old in enumerate(ranked_clusters)}
        for article in articles:
            if article.cluster_id is not None:
                article.cluster_id = remap.get(article.cluster_id, article.cluster_id)

        logger.info(
            "Clustered %d articles into %d topics (threshold=%.2f)",
            N, next_cluster, self.threshold,
        )
        return articles
