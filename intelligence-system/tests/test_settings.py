"""Tests for config/settings.py — validation, defaults, and env parsing."""

from __future__ import annotations

import os
import pytest


class TestDiscordConfig:
    def test_token_read_from_env(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok123")
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert cfg.token == "tok123"

    def test_digest_time_default(self, monkeypatch):
        monkeypatch.delenv("DIGEST_TIME_UTC", raising=False)
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert cfg.digest_time == "08:00"

    def test_digest_time_custom(self, monkeypatch):
        monkeypatch.setenv("DIGEST_TIME_UTC", "14:30")
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert cfg.digest_time == "14:30"

    def test_alert_interval_default_zero(self, monkeypatch):
        monkeypatch.delenv("ALERT_INTERVAL_HOURS", raising=False)
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert cfg.alert_interval_hours == 0

    def test_alert_interval_custom(self, monkeypatch):
        monkeypatch.setenv("ALERT_INTERVAL_HOURS", "6")
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert cfg.alert_interval_hours == 6

    def test_no_channel_id_fields(self):
        """Channel IDs were removed — DiscordConfig must not have them."""
        from config.settings import DiscordConfig
        cfg = DiscordConfig()
        assert not hasattr(cfg, "digest_channel_id"), (
            "digest_channel_id must not exist — channel is auto-discovered"
        )
        assert not hasattr(cfg, "alert_channel_id"), (
            "alert_channel_id must not exist — channel is auto-discovered"
        )


class TestCollectorConfig:
    def test_defaults(self, monkeypatch):
        for key in ("MAX_ITEMS_PER_PROVIDER", "DIGEST_TOP_N", "HTTP_TIMEOUT",
                    "MIN_RELEVANCE_SCORE", "DEDUP_THRESHOLD", "EXTRA_RSS_FEEDS"):
            monkeypatch.delenv(key, raising=False)
        from config.settings import CollectorConfig
        cfg = CollectorConfig()
        assert cfg.max_items_per_provider == 50
        assert cfg.digest_top_n == 8
        assert cfg.http_timeout == 20
        assert abs(cfg.min_relevance_score - 0.25) < 1e-9
        assert abs(cfg.dedup_threshold - 0.75) < 1e-9
        assert cfg.extra_rss_feeds == []

    def test_extra_rss_feeds_parsed(self, monkeypatch):
        monkeypatch.setenv("EXTRA_RSS_FEEDS", "https://a.com/rss,https://b.com/feed")
        from config.settings import CollectorConfig
        cfg = CollectorConfig()
        assert len(cfg.extra_rss_feeds) == 2
        assert "https://a.com/rss" in cfg.extra_rss_feeds

    def test_extra_rss_feeds_empty_string(self, monkeypatch):
        monkeypatch.setenv("EXTRA_RSS_FEEDS", "")
        from config.settings import CollectorConfig
        cfg = CollectorConfig()
        assert cfg.extra_rss_feeds == []


class TestSettingsValidation:
    def test_dry_run_skips_token_check(self):
        """validate() must not raise when DRY_RUN=true even with no token."""
        from config.settings import Settings
        s = Settings()
        s.dry_run = True
        s.discord.token = ""
        s.validate()  # must not raise

    def test_missing_token_raises(self):
        """validate() must raise when not dry-run and no token."""
        from config.settings import Settings
        s = Settings()
        s.dry_run = False
        s.discord.token = ""
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
            s.validate()

    def test_token_present_passes(self):
        from config.settings import Settings
        s = Settings()
        s.dry_run = False
        s.discord.token = "valid-token"
        s.validate()  # must not raise

    def test_no_channel_id_validation(self):
        """
        validate() must not reject a config that has no channel ID.
        Behavioral test: a Settings with a valid token and no channel IDs
        must pass validation.
        """
        from config.settings import Settings
        s = Settings()
        s.dry_run = False
        s.discord.token = "valid-token"
        # No channel IDs set — must not raise
        s.validate()

    def test_channel_id_fields_absent_from_discord_config(self):
        """Runtime contract: DiscordConfig instance must have no channel_id attrs."""
        from config.settings import Settings
        s = Settings()
        assert not hasattr(s.discord, "digest_channel_id")
        assert not hasattr(s.discord, "alert_channel_id")


class TestEnvHelpers:
    def test_env_bool_truthy_values(self, monkeypatch):
        from config.settings import _env_bool
        for val in ("1", "true", "yes", "on", "True", "YES"):
            monkeypatch.setenv("_TEST_BOOL", val)
            assert _env_bool("_TEST_BOOL") is True

    def test_env_bool_falsy_values(self, monkeypatch):
        from config.settings import _env_bool
        for val in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("_TEST_BOOL", val)
            assert _env_bool("_TEST_BOOL") is False

    def test_env_int_invalid_falls_back(self, monkeypatch):
        from config.settings import _env_int
        monkeypatch.setenv("_TEST_INT", "not_a_number")
        assert _env_int("_TEST_INT", 99) == 99

    def test_env_list_comma_split(self, monkeypatch):
        from config.settings import _env_list
        monkeypatch.setenv("_TEST_LIST", "a, b , c")
        result = _env_list("_TEST_LIST")
        assert result == ["a", "b", "c"]

    def test_env_list_empty(self, monkeypatch):
        from config.settings import _env_list
        monkeypatch.delenv("_TEST_LIST", raising=False)
        assert _env_list("_TEST_LIST") == []
