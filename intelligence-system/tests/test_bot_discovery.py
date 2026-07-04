"""
Tests for bot/discord_bot.py — channel auto-discovery logic.

All tests use lightweight mock objects; no real Discord connection is made.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from typing import Optional

from bot.discord_bot import IntelligenceBot, _CHANNEL_NAMES


# ---------------------------------------------------------------------------
# Helpers to build minimal discord mock objects
# ---------------------------------------------------------------------------

def _make_perms(send_messages: bool = True, embed_links: bool = True) -> MagicMock:
    perms = MagicMock()
    perms.send_messages = send_messages
    perms.embed_links = embed_links
    return perms


def _make_text_channel(name: str, writable: bool = True) -> MagicMock:
    ch = MagicMock()
    ch.name = name
    ch.permissions_for = MagicMock(return_value=_make_perms(writable, writable))
    ch.__class__ = __import__("discord").TextChannel
    return ch


def _make_guild(channels: list, bot_member: MagicMock | None = None) -> MagicMock:
    guild = MagicMock()
    guild.name = "Test Server"
    guild.text_channels = channels
    guild.me = bot_member or MagicMock()
    return guild


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChannelNames:
    def test_preferred_names_defined(self):
        assert "intelligence-digest" in _CHANNEL_NAMES
        assert "general" in _CHANNEL_NAMES

    def test_intelligence_digest_is_first(self):
        assert _CHANNEL_NAMES[0] == "intelligence-digest"

    def test_general_is_last_fallback(self):
        assert _CHANNEL_NAMES[-1] == "general"


class TestFindChannelInGuild:
    def _bot(self) -> IntelligenceBot:
        bot = IntelligenceBot.__new__(IntelligenceBot)
        return bot

    def test_prefers_intelligence_digest_over_general(self):
        bot = self._bot()
        general = _make_text_channel("general")
        digest = _make_text_channel("intelligence-digest")
        guild = _make_guild([general, digest])
        result = bot._find_channel_in_guild(guild)
        assert result.name == "intelligence-digest"

    def test_falls_back_through_priority_list(self):
        bot = self._bot()
        general = _make_text_channel("general")
        guild = _make_guild([general])
        result = bot._find_channel_in_guild(guild)
        assert result.name == "general"

    def test_falls_back_to_first_writable_when_no_preferred_name(self):
        bot = self._bot()
        random = _make_text_channel("random-chatter")
        guild = _make_guild([random])
        result = bot._find_channel_in_guild(guild)
        assert result.name == "random-chatter"

    def test_skips_unwritable_channels(self):
        bot = self._bot()
        readonly = _make_text_channel("intelligence-digest", writable=False)
        writable = _make_text_channel("general", writable=True)
        guild = _make_guild([readonly, writable])
        result = bot._find_channel_in_guild(guild)
        # intelligence-digest is not writable, so general is selected
        assert result.name == "general"

    def test_returns_none_when_no_writable_channel(self):
        bot = self._bot()
        readonly = _make_text_channel("general", writable=False)
        guild = _make_guild([readonly])
        result = bot._find_channel_in_guild(guild)
        assert result is None

    def test_returns_none_when_no_channels(self):
        bot = self._bot()
        guild = _make_guild([])
        result = bot._find_channel_in_guild(guild)
        assert result is None

    def test_case_insensitive_name_match(self):
        bot = self._bot()
        # Channel name in uppercase — must still match
        ch = _make_text_channel("INTELLIGENCE-DIGEST")
        guild = _make_guild([ch])
        result = bot._find_channel_in_guild(guild)
        assert result is not None
        assert result.name == "INTELLIGENCE-DIGEST"


class TestDiscoverDigestChannel:
    """
    `bot.guilds` is a read-only property on discord.py's Client.
    We patch it with PropertyMock so we can control the return value.
    """

    def test_returns_channel_from_first_guild(self):
        ch = _make_text_channel("intelligence-digest")
        guild = _make_guild([ch])
        bot = IntelligenceBot.__new__(IntelligenceBot)
        with patch.object(type(bot), "guilds", new_callable=PropertyMock, return_value=[guild]):
            result = bot._discover_digest_channel()
        assert result is not None
        assert result.name == "intelligence-digest"

    def test_returns_none_when_no_guilds(self):
        bot = IntelligenceBot.__new__(IntelligenceBot)
        with patch.object(type(bot), "guilds", new_callable=PropertyMock, return_value=[]):
            result = bot._discover_digest_channel()
        assert result is None

    def test_returns_none_when_all_guilds_have_no_writable_channel(self):
        readonly = _make_text_channel("general", writable=False)
        guild = _make_guild([readonly])
        bot = IntelligenceBot.__new__(IntelligenceBot)
        with patch.object(type(bot), "guilds", new_callable=PropertyMock, return_value=[guild]):
            result = bot._discover_digest_channel()
        assert result is None

    def test_walks_multiple_guilds_until_channel_found(self):
        empty_guild = _make_guild([])
        good_guild = _make_guild([_make_text_channel("osint")])
        bot = IntelligenceBot.__new__(IntelligenceBot)
        with patch.object(type(bot), "guilds", new_callable=PropertyMock, return_value=[empty_guild, good_guild]):
            result = bot._discover_digest_channel()
        assert result is not None
        assert result.name == "osint"


class TestSendDigestNoChannel:
    """send_digest must return False gracefully when no channel is available."""

    @pytest.mark.asyncio
    async def test_send_digest_returns_false_when_no_channel(self):
        bot = IntelligenceBot.__new__(IntelligenceBot)
        bot._digest_channel = None

        from core.digest import DigestReport
        from datetime import datetime, timezone
        report = DigestReport(
            sections=[],
            generated_at=datetime.now(timezone.utc),
            total_collected=0,
            total_after_dedup=0,
            total_in_digest=0,
        )
        result = await bot.send_digest(report)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_returns_false_when_no_channel(self):
        bot = IntelligenceBot.__new__(IntelligenceBot)
        bot._digest_channel = None
        result = await bot.send_alert([])
        assert result is False
