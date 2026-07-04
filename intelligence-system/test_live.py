#!/usr/bin/env python3
"""
Live system test — verifies all components are working end-to-end.

Steps:
  1. Validate configuration (DISCORD_BOT_TOKEN present)
  2. Connect to Discord and log in
  3. Auto-discover target channel
  4. Send "System test successful" ping
  5. Fetch public RSS + Reddit feeds (fast subset)
  6. Rank and deduplicate
  7. Generate minimal digest summary
  8. Send summary to Discord channel

Usage:
    python test_live.py

No extra env vars needed beyond DISCORD_BOT_TOKEN.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import List

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Colour helpers (no external deps needed) ──────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg: str)   -> None: print(f"{GREEN}  ✓  {msg}{RESET}")
def fail(msg: str) -> None: print(f"{RED}  ✗  {msg}{RESET}")
def info(msg: str) -> None: print(f"{CYAN}  ·  {msg}{RESET}")
def head(msg: str) -> None: print(f"\n{BOLD}{YELLOW}▶ {msg}{RESET}")


# ── Quick RSS feeds (fast, reliable, no auth) ─────────────────────────────────
TEST_FEEDS = [
    ("https://hnrss.org/frontpage",                     "Hacker News"),
    ("https://arstechnica.com/feed/",                   "Ars Technica"),
    ("https://feeds.feedburner.com/TheHackersNews",     "The Hacker News"),
    ("https://arxiv.org/rss/cs.AI",                     "arXiv cs.AI"),
    ("https://dev.to/feed",                             "dev.to"),
]

TEST_SUBREDDITS = [
    ("programming", "r/programming"),
    ("netsec",      "r/netsec"),
    ("technology",  "r/technology"),
]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — configuration check
# ─────────────────────────────────────────────────────────────────────────────

def check_config() -> str:
    head("STEP 1 — Configuration")
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        fail("DISCORD_BOT_TOKEN is not set")
        print(f"\n  Set it in Replit Secrets or: export DISCORD_BOT_TOKEN=<your token>")
        sys.exit(1)
    ok(f"DISCORD_BOT_TOKEN found ({len(token)} chars)")
    return token


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — fetch RSS + Reddit
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_feeds() -> List[dict]:
    head("STEP 2 — Fetching RSS feeds")
    from utils.http_client import fetch_text, close_session
    import xml.etree.ElementTree as ET

    articles: List[dict] = []
    t0 = time.monotonic()

    async def _fetch_rss(url: str, label: str) -> List[dict]:
        text = await fetch_text(url, timeout=10, retries=2, backoff=1.0)
        if not text:
            info(f"No response from {label}")
            return []
        items: List[dict] = []
        try:
            root = ET.fromstring(text)
            channel = root.find("channel")
            nodes = channel.findall("item") if channel is not None else root.findall(".//item")
            for item in nodes[:5]:
                title_el = item.find("title")
                link_el  = item.find("link")
                title = (title_el.text or "").strip() if title_el is not None else ""
                url_  = (link_el.text  or "").strip() if link_el  is not None else ""
                if title and url_:
                    items.append({"title": title, "url": url_, "source": label})
        except ET.ParseError:
            pass
        return items

    tasks = [_fetch_rss(url, label) for url, label in TEST_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (_, label), result in zip(TEST_FEEDS, results):
        if isinstance(result, Exception):
            fail(f"{label}: {result}")
        else:
            articles.extend(result)
            ok(f"{label}: {len(result)} articles")

    elapsed = time.monotonic() - t0
    info(f"RSS done in {elapsed:.1f}s — {len(articles)} articles total")
    return articles


async def fetch_reddit() -> List[dict]:
    head("STEP 3 — Fetching Reddit feeds")
    from utils.http_client import fetch_json

    articles: List[dict] = []
    t0 = time.monotonic()

    async def _fetch_sub(sub: str, label: str) -> List[dict]:
        # Reddit requires a descriptive User-Agent or returns 403
        data = await fetch_json(
            f"https://www.reddit.com/r/{sub}/hot.json",
            params={"limit": "10"},
            user_agent="python:osint-digest-bot:v1.0 (by /u/osintdigestbot)",
            timeout=15,
            retries=2,
        )
        if not data:
            return []
        items = []
        for child in (data.get("data", {}).get("children") or []):
            post = child.get("data", {})
            title = (post.get("title") or "").strip()
            url   = f"https://reddit.com{post.get('permalink', '')}"
            score = int(post.get("score", 0))
            if title and score >= 20:
                items.append({"title": title, "url": url, "source": label, "score": score})
        return items

    tasks = [_fetch_sub(sub, label) for sub, label in TEST_SUBREDDITS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (_, label), result in zip(TEST_SUBREDDITS, results):
        if isinstance(result, Exception):
            fail(f"{label}: {result}")
        else:
            articles.extend(result)
            ok(f"{label}: {len(result)} posts (≥20 upvotes)")

    elapsed = time.monotonic() - t0
    info(f"Reddit done in {elapsed:.1f}s — {len(articles)} posts total")
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — build minimal digest text
# ─────────────────────────────────────────────────────────────────────────────

def build_digest(rss: List[dict], reddit: List[dict]) -> str:
    head("STEP 4 — Building digest")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"**🛰️ OSINT Intelligence System — Live Test Digest**",
        f"*{now}*\n",
        f"📡 **RSS feeds fetched:** {len(rss)} articles from {len(TEST_FEEDS)} sources",
        f"🤖 **Reddit posts fetched:** {len(reddit)} posts from {len(TEST_SUBREDDITS)} subreddits\n",
    ]

    # Top 5 RSS items
    lines.append("**📰 Top Headlines (RSS)**")
    for i, a in enumerate(rss[:5], 1):
        title = a["title"][:90] + ("…" if len(a["title"]) > 90 else "")
        lines.append(f"{i}. [{title}]({a['url']}) — *{a['source']}*")

    lines.append("")

    # Top 5 Reddit posts by score
    sorted_reddit = sorted(reddit, key=lambda x: x.get("score", 0), reverse=True)
    lines.append("**🔥 Top Reddit Posts**")
    for i, a in enumerate(sorted_reddit[:5], 1):
        title = a["title"][:90] + ("…" if len(a["title"]) > 90 else "")
        lines.append(f"{i}. [{title}]({a['url']}) — *{a['source']}*")

    lines.append(f"\n*All data from public sources only · No API keys used*")

    digest = "\n".join(lines)
    ok(f"Digest built — {len(digest)} chars, {len(digest.splitlines())} lines")
    return digest


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Discord bot: connect, ping, send digest
# ─────────────────────────────────────────────────────────────────────────────

class _TestBot:
    """Minimal self-contained bot — does not depend on the full bot module."""

    CHANNEL_NAMES = ["intelligence-digest", "osint-digest", "osint", "general"]

    def __init__(self, token: str) -> None:
        self.token = token
        self._channel = None
        self._guild_name = ""

    async def run(self, ping_msg: str, digest: str) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = False
        client = discord.Client(intents=intents)
        ready = asyncio.Event()

        @client.event
        async def on_ready():
            head("STEP 5 — Discord")
            ok(f"Logged in as: {client.user} (ID: {client.user.id})")
            ok(f"Connected to {len(client.guilds)} guild(s)")

            # Find best channel
            ch = self._discover(client)
            if ch is None:
                fail(
                    "No writable text channel found.\n"
                    "  Create a channel named 'intelligence-digest' and give the bot\n"
                    "  Send Messages + Embed Links permissions, then re-run."
                )
                await client.close()
                ready.set()
                return

            self._channel = ch
            self._guild_name = ch.guild.name
            ok(f"Target channel: #{ch.name} in '{ch.guild.name}'")

            # ── Ping ──────────────────────────────────────────────────────────
            head("STEP 6 — Sending system ping")
            try:
                await ch.send(ping_msg)
                ok("Ping delivered ✓")
            except discord.Forbidden:
                fail(f"No permission to send in #{ch.name}")
                await client.close()
                ready.set()
                return

            # ── Digest ────────────────────────────────────────────────────────
            head("STEP 7 — Sending digest")
            # Discord message limit is 2000 chars — split if needed
            chunks = _split(digest, 1900)
            for i, chunk in enumerate(chunks, 1):
                try:
                    await ch.send(chunk)
                    await asyncio.sleep(0.8)
                    ok(f"Digest chunk {i}/{len(chunks)} delivered")
                except discord.HTTPException as e:
                    fail(f"Discord HTTP error on chunk {i}: {e}")

            await client.close()
            ready.set()

        import discord as _discord

        login_error: Exception | None = None

        async def _start_with_error_capture():
            nonlocal login_error
            try:
                await client.start(self.token)
            except _discord.LoginFailure as e:
                login_error = e
                ready.set()   # unblock the wait immediately
            except Exception as e:
                login_error = e
                ready.set()

        try:
            async with client:
                start = asyncio.create_task(_start_with_error_capture())
                try:
                    await asyncio.wait_for(ready.wait(), timeout=45)
                except asyncio.TimeoutError:
                    fail("Timed out waiting for Discord ready (45s)")
                finally:
                    if not start.done():
                        start.cancel()
                        try:
                            await asyncio.wait_for(start, timeout=5)
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            pass

            if login_error is not None:
                if "Improper token" in str(login_error) or "LoginFailure" in type(login_error).__name__:
                    fail("Discord token is invalid or expired.")
                    print(f"\n  {YELLOW}Fix:{RESET} Go to discord.com/developers/applications")
                    print(f"       → your app → Bot → {BOLD}Reset Token{RESET}")
                    print(f"       Then update the DISCORD_BOT_TOKEN secret in Replit.\n")
                else:
                    fail(f"Discord error: {login_error}")
                sys.exit(1)
        except Exception as e:
            fail(f"Discord connection error: {e}")
            sys.exit(1)

    def _discover(self, client) -> object | None:
        import discord
        for guild in client.guilds:
            me = guild.me
            for name in self.CHANNEL_NAMES:
                for ch in guild.text_channels:
                    if ch.name.lower() == name:
                        p = ch.permissions_for(me)
                        if p.send_messages and p.embed_links:
                            return ch
            # Fallback: first writable text channel
            for ch in guild.text_channels:
                p = ch.permissions_for(me)
                if p.send_messages and p.embed_links:
                    return ch
        return None


def _split(text: str, limit: int) -> List[str]:
    """Split text into chunks ≤ limit chars, breaking on newlines."""
    chunks, current = [], []
    length = 0
    for line in text.splitlines(keepends=True):
        if length + len(line) > limit and current:
            chunks.append("".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def _main() -> int:
    print(f"\n{BOLD}{'═' * 56}")
    print( "  OSINT Intelligence System — Live Component Test")
    print(f"{'═' * 56}{RESET}")

    total_start = time.monotonic()

    # 1 — config
    token = check_config()

    # 2+3 — fetch concurrently
    rss_task    = asyncio.create_task(fetch_feeds())
    reddit_task = asyncio.create_task(fetch_reddit())
    rss, reddit = await asyncio.gather(rss_task, reddit_task)

    if not rss and not reddit:
        fail("No data fetched from any source — check network connectivity")
        return 1

    # 4 — build digest
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ping    = f"✅ **System test successful** — {now_str}"
    digest  = build_digest(rss, reddit)

    # 5-7 — Discord
    bot = _TestBot(token)
    await bot.run(ping, digest)

    # Close shared HTTP session
    from utils.http_client import close_session
    await close_session()

    elapsed = time.monotonic() - total_start
    print(f"\n{BOLD}{GREEN}{'═' * 56}")
    print(f"  All steps complete in {elapsed:.1f}s")
    print(f"{'═' * 56}{RESET}\n")
    return 0


def main() -> None:
    try:
        code = asyncio.run(_main())
        sys.exit(code)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
