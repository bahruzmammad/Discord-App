"""
Configuration management — reads from environment variables / .env file.
All settings have sensible defaults so the system runs without any API keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def _env_list(key: str, default: str = "") -> List[str]:
    raw = os.environ.get(key, default).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class DiscordConfig:
    token: str = field(default_factory=lambda: _env("DISCORD_BOT_TOKEN"))
    digest_channel_id: int = field(
        default_factory=lambda: _env_int("DISCORD_DIGEST_CHANNEL_ID", 0)
    )
    alert_channel_id: int = field(
        default_factory=lambda: _env_int(
            "DISCORD_ALERT_CHANNEL_ID",
            _env_int("DISCORD_DIGEST_CHANNEL_ID", 0),
        )
    )
    # Digest delivery time in HH:MM (UTC)
    digest_time: str = field(default_factory=lambda: _env("DIGEST_TIME_UTC", "08:00"))
    # Interval in hours for trending alerts (0 = disabled)
    alert_interval_hours: int = field(
        default_factory=lambda: _env_int("ALERT_INTERVAL_HOURS", 0)
    )


@dataclass
class CollectorConfig:
    # Maximum items to retain per provider per cycle
    max_items_per_provider: int = field(
        default_factory=lambda: _env_int("MAX_ITEMS_PER_PROVIDER", 50)
    )
    # Number of top articles per category in digest
    digest_top_n: int = field(
        default_factory=lambda: _env_int("DIGEST_TOP_N", 8)
    )
    # HTTP request timeout in seconds
    http_timeout: int = field(
        default_factory=lambda: _env_int("HTTP_TIMEOUT", 20)
    )
    # Minimum relevance score to include in digest (0.0–1.0)
    min_relevance_score: float = field(
        default_factory=lambda: float(_env("MIN_RELEVANCE_SCORE", "0.25"))
    )
    # Deduplication similarity threshold (0.0–1.0)
    dedup_threshold: float = field(
        default_factory=lambda: float(_env("DEDUP_THRESHOLD", "0.75"))
    )
    # Extra RSS feed URLs (comma-separated) to add at runtime
    extra_rss_feeds: List[str] = field(
        default_factory=lambda: _env_list("EXTRA_RSS_FEEDS")
    )
    # User-Agent string for HTTP requests
    user_agent: str = field(
        default_factory=lambda: _env(
            "HTTP_USER_AGENT",
            "OSINTDigestBot/1.0 (+https://github.com/your-org/osint-digest)",
        )
    )


@dataclass
class LogConfig:
    level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())
    format: str = field(
        default_factory=lambda: _env("LOG_FORMAT", "rich")  # "rich" | "json" | "plain"
    )
    file: Optional[str] = field(
        default_factory=lambda: _env("LOG_FILE", "") or None
    )


@dataclass
class Settings:
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    log: LogConfig = field(default_factory=LogConfig)
    # Run in dry-run mode: collect and process but do not post to Discord
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))
    # Run a single digest cycle immediately on startup then exit
    run_once: bool = field(default_factory=lambda: _env_bool("RUN_ONCE", False))

    def validate(self) -> None:
        """Raise ValueError for obviously broken config."""
        if not self.dry_run and not self.discord.token:
            raise ValueError(
                "DISCORD_BOT_TOKEN is required unless DRY_RUN=true. "
                "Copy .env.example to .env and fill in your token."
            )
        if not self.dry_run and not self.discord.digest_channel_id:
            raise ValueError(
                "DISCORD_DIGEST_CHANNEL_ID is required unless DRY_RUN=true."
            )


# Singleton — import this everywhere
settings = Settings()
