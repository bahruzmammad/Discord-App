#!/usr/bin/env python3
"""
OSINT Intelligence System — entry point.

Modes:
  Default          Start the Discord bot + scheduler (runs indefinitely).
  DRY_RUN=true     Collect, process, and log to stdout — no Discord needed.
  RUN_ONCE=true    Run a single digest cycle then exit.

Usage:
  python main.py
  DRY_RUN=true python main.py
  RUN_ONCE=true python main.py
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

# Bootstrap path so all imports work from this directory
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from utils.logger import setup_logging, get_logger

# Logging must be set up before any other imports that use it
setup_logging(
    level=settings.log.level,
    fmt=settings.log.format,
    log_file=settings.log.file,
)

logger = get_logger("main")


async def _run_bot_mode() -> None:
    """Start the full Discord bot with background scheduler."""
    from bot.discord_bot import create_bot
    from core.pipeline import IntelligencePipeline
    from scheduler.jobs import JobScheduler
    from services.intelligence_service import IntelligenceService
    from utils.http_client import close_session

    bot = create_bot()
    pipeline = IntelligencePipeline()
    service = IntelligenceService(pipeline=pipeline, bot=bot)
    scheduler = JobScheduler()
    scheduler.register(service)

    stop_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Received signal %s — initiating shutdown", sig.name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    async def _bot_runner() -> None:
        bot_task: asyncio.Task | None = None
        try:
            async with bot:
                # Spawn bot.start() as a tracked task so we can cancel it on shutdown
                bot_task = asyncio.create_task(
                    bot.start(settings.discord.token), name="discord-bot-start"
                )
                if not await bot.wait_until_ready_custom(timeout=60):
                    logger.error("Bot did not connect within 60 seconds")
                    stop_event.set()
                    return
                scheduler.start()
                # Wait until a shutdown signal is received
                await stop_event.wait()
        except Exception as exc:
            logger.error("Bot runner error: %s", exc, exc_info=True)
            stop_event.set()
        finally:
            scheduler.stop()
            # Cancel the bot task cleanly to avoid orphaned coroutines
            if bot_task and not bot_task.done():
                bot_task.cancel()
                try:
                    await asyncio.wait_for(bot_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            await close_session()

    await _bot_runner()


async def _run_dry_run() -> None:
    """Single collection + processing cycle; output to stdout only."""
    from core.pipeline import IntelligencePipeline
    from bot.formatter import format_plain_digest
    from services.intelligence_service import IntelligenceService
    from utils.http_client import close_session

    logger.info("Running in DRY_RUN mode — no Discord connection")
    pipeline = IntelligencePipeline()
    service = IntelligenceService(pipeline=pipeline, bot=None)
    try:
        await service.deliver_digest()
    finally:
        await close_session()


async def _run_once() -> None:
    """Run one full digest cycle and post to Discord, then exit."""
    from bot.discord_bot import create_bot
    from core.pipeline import IntelligencePipeline
    from services.intelligence_service import IntelligenceService
    from utils.http_client import close_session

    logger.info("Running in RUN_ONCE mode")
    bot = create_bot()
    pipeline = IntelligencePipeline()
    service = IntelligenceService(pipeline=pipeline, bot=bot)

    start_task: asyncio.Task | None = None
    try:
        async with bot:
            start_task = asyncio.create_task(
                bot.start(settings.discord.token), name="discord-bot-start-once"
            )
            if not await bot.wait_until_ready_custom(timeout=60):
                logger.error("Bot did not connect — aborting")
                return
            await service.deliver_digest()
            await bot.graceful_shutdown()
    finally:
        # Cancel tracked bot task to avoid orphaned coroutines
        if start_task and not start_task.done():
            start_task.cancel()
            try:
                await asyncio.wait_for(start_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        await close_session()


def main() -> int:
    try:
        settings.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    logger.info(
        "OSINT Intelligence System starting | dry_run=%s run_once=%s",
        settings.dry_run, settings.run_once,
    )

    try:
        if settings.dry_run:
            asyncio.run(_run_dry_run())
        elif settings.run_once:
            asyncio.run(_run_once())
        else:
            asyncio.run(_run_bot_mode())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as exc:
        logger.critical("Fatal error: %s", exc, exc_info=True)
        return 1

    logger.info("OSINT Intelligence System stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
