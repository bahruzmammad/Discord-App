"""
Security & CVE feed provider.

Pulls from:
- NIST NVD (National Vulnerability Database) public API v2 — no key needed
- CISA Known Exploited Vulnerabilities catalog (public JSON)
- US-CERT / CISA alerts RSS
- GitHub Security Advisories public API
- Exploit-DB RSS (educational/public)
- Full-Disclosure mailing list RSS
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from config.settings import settings
from models.article import Article, Category, utcnow
from providers.base import BaseProvider
from utils.http_client import fetch_json, fetch_text

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime


def _parse_date(raw: Optional[str]) -> datetime:
    if not raw:
        return utcnow()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return utcnow()


class SecurityProvider(BaseProvider):
    """Aggregates cybersecurity and vulnerability intelligence from public sources."""

    name = "security"

    # CISA KEV — public JSON, no auth
    _CISA_KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    # NVD API v2 — public, no auth required for basic queries
    _NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    # GitHub Security Advisories — public GraphQL/REST
    _GHSA_API = "https://api.github.com/advisories"

    # RSS feeds (educational / defensive security)
    _RSS_FEEDS = [
        ("https://www.exploit-db.com/rss.xml", "Exploit-DB"),
        ("https://seclists.org/rss/fulldisclosure.rss", "Full Disclosure"),
        ("https://www.securityfocus.com/rss/vulnerabilities.xml", "SecurityFocus"),
    ]

    async def _fetch_nvd_recent(self) -> List[Article]:
        """Fetch CVEs published in the last 7 days from NVD v2 API."""
        pub_start = (utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000")
        pub_end = utcnow().strftime("%Y-%m-%dT23:59:59.999")

        data = await fetch_json(
            self._NVD_API,
            params={
                "pubStartDate": pub_start,
                "pubEndDate": pub_end,
                "resultsPerPage": 30,
                "startIndex": 0,
            },
            user_agent=settings.collector.user_agent,
            timeout=30,
        )
        if not data or "vulnerabilities" not in data:
            return []

        articles: List[Article] = []
        for vuln in data.get("vulnerabilities", []):
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")
            if not cve_id:
                continue

            desc_list = cve.get("descriptions", [])
            description = next(
                (d["value"] for d in desc_list if d.get("lang") == "en"), ""
            )

            # CVSS score for raw_score
            metrics = cve.get("metrics", {})
            cvss_score = 0.0
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                metric_list = metrics.get(key, [])
                if metric_list:
                    try:
                        cvss_score = float(
                            metric_list[0]["cvssData"]["baseScore"]
                        )
                    except (KeyError, IndexError, TypeError):
                        pass
                    break

            pub_date = _parse_date(cve.get("published", ""))
            severity = "CRITICAL" if cvss_score >= 9 else "HIGH" if cvss_score >= 7 else "MEDIUM" if cvss_score >= 4 else "LOW"

            articles.append(
                Article(
                    title=f"{cve_id} [{severity}] — {description[:100]}",
                    url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    source="NVD / NIST",
                    category=Category.CYBERSECURITY,
                    timestamp=pub_date,
                    summary=description[:400] or None,
                    raw_score=cvss_score,
                    tags=[cve_id, severity.lower(), "cve"],
                    provider="security",
                )
            )

        return articles

    async def _fetch_cisa_kev(self) -> List[Article]:
        """Fetch CISA Known Exploited Vulnerabilities (most recent 20)."""
        data = await fetch_json(
            self._CISA_KEV,
            user_agent=settings.collector.user_agent,
            timeout=settings.collector.http_timeout,
        )
        if not data or "vulnerabilities" not in data:
            return []

        vulns = data["vulnerabilities"]
        # Sort by dateAdded descending, take most recent 20
        try:
            vulns = sorted(vulns, key=lambda v: v.get("dateAdded", ""), reverse=True)[:20]
        except Exception:
            vulns = vulns[:20]

        articles: List[Article] = []
        cutoff = utcnow() - timedelta(days=14)
        for v in vulns:
            date_added = _parse_date(v.get("dateAdded", ""))
            if date_added < cutoff:
                continue
            cve_id = v.get("cveID", "")
            vendor = v.get("vendorProject", "")
            product = v.get("product", "")
            vuln_name = v.get("vulnerabilityName", "")
            due_date = v.get("dueDate", "")

            articles.append(
                Article(
                    title=f"[KEV] {cve_id} — {vuln_name} ({vendor} {product})",
                    url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                    source="CISA KEV",
                    category=Category.CYBERSECURITY,
                    timestamp=date_added,
                    summary=(
                        f"CISA has added {cve_id} to the Known Exploited Vulnerabilities catalog. "
                        f"Remediation due: {due_date}. "
                        f"Required action: {v.get('requiredAction', 'Apply vendor patch.')}"
                    ),
                    raw_score=9.0,  # KEV entries are high severity by definition
                    tags=[cve_id, "kev", "cisa", "actively-exploited"],
                    provider="security",
                )
            )

        return articles

    async def _fetch_ghsa(self) -> List[Article]:
        """Fetch GitHub Security Advisories (public API)."""
        data = await fetch_json(
            self._GHSA_API,
            params={"per_page": 20, "type": "reviewed", "severity": "high,critical"},
            user_agent="OSINTDigestBot/1.0",
            timeout=settings.collector.http_timeout,
        )
        if not isinstance(data, list):
            return []

        articles: List[Article] = []
        cutoff = utcnow() - timedelta(days=14)
        for adv in data[:20]:
            published = _parse_date(adv.get("published_at", ""))
            if published < cutoff:
                continue
            ghsa_id = adv.get("ghsa_id", "")
            summary = adv.get("summary", "")
            severity = adv.get("severity", "").upper()
            url = adv.get("html_url") or f"https://github.com/advisories/{ghsa_id}"
            cve_id = adv.get("cve_id") or ""

            articles.append(
                Article(
                    title=f"[GHSA] {ghsa_id} [{severity}] — {summary[:100]}",
                    url=url,
                    source="GitHub Security Advisories",
                    category=Category.CYBERSECURITY,
                    timestamp=published,
                    summary=adv.get("description", summary)[:400] or None,
                    raw_score={"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.5}.get(
                        severity.lower(), 5.0
                    ),
                    tags=list(filter(None, [ghsa_id, cve_id, "github", severity.lower()])),
                    provider="security",
                )
            )

        return articles

    async def _fetch_rss(self, url: str, source: str) -> List[Article]:
        text = await fetch_text(url, user_agent=settings.collector.user_agent, timeout=settings.collector.http_timeout)
        if not text:
            return []

        articles: List[Article] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")
        for item in items[:15]:
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            desc_el = item.find("description")

            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            date_raw = (date_el.text or "") if date_el is not None else ""
            desc = re.sub(r"<[^>]+>", " ", (desc_el.text or "") if desc_el is not None else "")[:400].strip()

            if not title or not link:
                continue

            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=source,
                    category=Category.CYBERSECURITY,
                    timestamp=_parse_date(date_raw),
                    summary=desc or None,
                    provider="security",
                )
            )

        return articles

    async def fetch(self) -> List[Article]:
        tasks = [
            asyncio.create_task(self._fetch_nvd_recent()),
            asyncio.create_task(self._fetch_cisa_kev()),
            asyncio.create_task(self._fetch_ghsa()),
        ]
        for url, src in self._RSS_FEEDS:
            tasks.append(asyncio.create_task(self._fetch_rss(url, src)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: List[Article] = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.warning("Security feed error: %s", r)
            else:
                articles.extend(r)

        return articles
