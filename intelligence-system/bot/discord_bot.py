"""
Discord bot layer.

Handles:
- Connection and readiness
- Auto-discovery of the digest channel by name (no channel ID required)
- Sending digest embeds to that channel
- Sending trending alerts
- Graceful shutdown

Channel discovery order (case-insensitive):
  1. "intelligence-digest"
  2. "osint-digest"
  3. "osint"
  4. "general"
  5. First writable text channel in the first guild
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import discord
from discord.ext import commands

from bot.formatter import (
    build_digest_footer,
    build_digest_header,
    build_section_embeds,
    build_trending_alert,
)
from core.digest import DigestReport
from models.article import Article

logger = logging.getLogger(__name__)

# Delay between embed sends to avoid Discord rate-limits (seconds)
_INTER_EMBED_DELAY = 0.6
_INTER_SECTION_DELAY = 1.2

# Channel names tried in order when auto-discovering
_CHANNEL_NAMES = ["intelligence-digest", "osint-digest", "osint", "general"]


def _make_embed(data: dict) -> discord.Embed:
    """Convert a formatter dict to a discord.Embed."""
    embed = discord.Embed(
        title=data.get("title", ""),
        description=data.get("description", ""),
        color=data.get("color", 0x2C3E50),
    )
    for field in data.get("fields", []):
        embed.add_field(
            name=field.get("name", "\u200b"),
            value=field.get("value", "\u200b"),
            inline=field.get("inline", False),
        )
    footer = data.get("footer")
    if footer:
        embed.set_footer(text=footer.get("text", ""))
    return embed


class IntelligenceBot(commands.Bot):
    """Discord bot that delivers intelligence digests."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = False  # No message reading needed
        super().__init__(command_prefix="!", intents=intents)
        self._ready_event = asyncio.Event()
        self._digest_channel: Optional[discord.TextChannel] = None

    # ------------------------------------------------------------------
    # Channel discovery
    # ------------------------------------------------------------------

    def _find_channel_in_guild(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Return the best writable text channel in *guild*."""
        me = guild.me

        def can_write(ch: discord.TextChannel) -> bool:
            perms = ch.permissions_for(me)
            return perms.send_messages and perms.embed_links

        # Try preferred names first
        for name in _CHANNEL_NAMES:
            for ch in guild.text_channels:
                if ch.name.lower() == name and can_write(ch):
                    return ch

        # Fall back to any writable text channel
        for ch in guild.text_channels:
            if can_write(ch):
                return ch

        return None

    def _discover_digest_channel(self) -> Optional[discord.TextChannel]:
        """Walk all guilds and return the first suitable channel found."""
        for guild in self.guilds:
            ch = self._find_channel_in_guild(guild)
            if ch is not None:
                return ch
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_ready(self) -> None:
        logger.info("Discord bot ready — logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the intelligence feed",
            )
        )
        self._digest_channel = self._discover_digest_channel()
        if self._digest_channel:
            logger.info(
                "Digest channel auto-selected: #%s in '%s'",
                self._digest_channel.name,
                self._digest_channel.guild.name,
            )
        else:
            logger.warning(
                "No writable text channel found — bot is in %d guild(s). "
                "Create a channel named 'intelligence-digest' and reinvite the bot "
                "with Send Messages + Embed Links permissions.",
                len(self.guilds),
            )
        self._ready_event.set()

    async def wait_until_ready_custom(self, timeout: float = 30.0) -> bool:
        """Wait for the bot to be fully connected. Returns False on timeout."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for Discord bot to become ready")
            return False

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    async def send_digest(self, report: DigestReport) -> bool:
        """
        Send the full intelligence digest to the auto-discovered digest channel.

        Returns True on success, False on failure.
        """
        channel = self._digest_channel
        if channel is None:
            logger.error(
                "No digest channel available — cannot deliver digest. "
                "Ensure the bot has been invited to a server with a writable text channel."
            )
            return False

        logger.info("Sending digest to #%s (%s)", channel.name, channel.guild.name)

        try:
            # 1. Header
            header_embed = _make_embed(build_digest_header(report))
            await channel.send(embed=header_embed)
            await asyncio.sleep(_INTER_EMBED_DELAY)

            # 2. Sections
            for section in report.sections:
                section_embeds = build_section_embeds(section)
                for embed_data in section_embeds:
                    embed = _make_embed(embed_data)
                    await channel.send(embed=embed)
                    await asyncio.sleep(_INTER_EMBED_DELAY)
                await asyncio.sleep(_INTER_SECTION_DELAY)

            # 3. Footer
            footer_embed = _make_embed(build_digest_footer(report))
            await channel.send(embed=footer_embed)

            logger.info(
                "Digest delivered: %d sections, %d articles",
                len(report.sections), report.total_in_digest,
            )
            return True

        except discord.Forbidden:
            logger.error("No permission to send messages in #%s", channel.name)
            return False
        except discord.HTTPException as exc:
            logger.error("Discord HTTP error during digest delivery: %s", exc)
            return False

    async def send_alert(self, articles: List[Article], top_n: int = 5) -> bool:
        """Send a trending alert to the digest channel."""
        channel = self._digest_channel
        if channel is None:
            logger.error("No channel available for trending alert")
            return False

        embeds_data = build_trending_alert(articles, top_n=top_n)
        try:
            for embed_data in embeds_data:
                await channel.send(embed=_make_embed(embed_data))
                await asyncio.sleep(_INTER_EMBED_DELAY)
            return True
        except Exception as exc:
            logger.error("Alert delivery failed: %s", exc)
            return False

    async def graceful_shutdown(self) -> None:
        """Close the bot connection cleanly."""
        logger.info("Shutting down Discord bot")
        await self.close()


def create_bot() -> IntelligenceBot:
    """Factory function — returns a configured IntelligenceBot instance."""
    return IntelligenceBot()
