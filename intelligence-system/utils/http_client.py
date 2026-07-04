"""
Async HTTP client with retries, rate-limiting, and a shared aiohttp session.
All providers import and use `fetch_text` / `fetch_json` from here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)

# One shared session for the lifetime of the process
_session: Optional[ClientSession] = None

# Minimum seconds between requests to the same hostname
_RATE_LIMIT_SECONDS: float = 1.0
_last_request: Dict[str, float] = {}
_rate_lock = asyncio.Lock()

DEFAULT_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/html, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


async def get_session(user_agent: str = "OSINTDigestBot/1.0", timeout: int = 20) -> ClientSession:
    """Return (or lazily create) the shared async HTTP session."""
    global _session
    if _session is None or _session.closed:
        connector = TCPConnector(limit=30)  # ssl=True by default — never disable certificate verification
        _session = ClientSession(
            connector=connector,
            timeout=ClientTimeout(total=timeout),
            headers={**DEFAULT_HEADERS, "User-Agent": user_agent},
        )
    return _session


async def close_session() -> None:
    """Gracefully close the shared session on shutdown."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def _rate_limit(url: str) -> None:
    """Enforce per-hostname rate limiting."""
    host = urlparse(url).netloc
    async with _rate_lock:
        now = asyncio.get_event_loop().time()
        last = _last_request.get(host, 0.0)
        wait = _RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request[host] = asyncio.get_event_loop().time()


async def fetch_text(
    url: str,
    *,
    user_agent: str = "OSINTDigestBot/1.0",
    timeout: int = 20,
    retries: int = 3,
    backoff: float = 2.0,
) -> Optional[str]:
    """Fetch URL and return raw text, or None on failure."""
    session = await get_session(user_agent, timeout)
    await _rate_limit(url)

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text(errors="replace")
                if resp.status in (429, 503):
                    wait = backoff ** attempt
                    logger.warning("Rate limited by %s (HTTP %d), waiting %.1fs", url, resp.status, wait)
                    await asyncio.sleep(wait)
                    continue
                logger.warning("HTTP %d for %s", resp.status, url)
                return None
        except asyncio.TimeoutError:
            logger.warning("Timeout fetching %s (attempt %d/%d)", url, attempt, retries)
        except aiohttp.ClientError as exc:
            logger.warning("Client error fetching %s: %s (attempt %d/%d)", url, exc, attempt, retries)
        if attempt < retries:
            await asyncio.sleep(backoff ** attempt)

    logger.error("All %d attempts failed for %s", retries, url)
    return None


async def fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    user_agent: str = "OSINTDigestBot/1.0",
    timeout: int = 20,
    retries: int = 3,
) -> Optional[Any]:
    """Fetch URL and return parsed JSON, or None on failure."""
    session = await get_session(user_agent, timeout)
    await _rate_limit(url)

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                logger.warning("HTTP %d for %s", resp.status, url)
                return None
        except asyncio.TimeoutError:
            logger.warning("Timeout fetching JSON %s (attempt %d/%d)", url, attempt, retries)
        except (aiohttp.ClientError, Exception) as exc:
            logger.warning("Error fetching JSON %s: %s", url, exc)
        if attempt < retries:
            await asyncio.sleep(2.0 ** attempt)

    return None
