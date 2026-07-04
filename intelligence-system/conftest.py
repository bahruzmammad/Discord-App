"""Pytest configuration and shared fixtures."""

import os
import sys
import pytest

# Ensure the project root is on sys.path so all imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set minimal environment for tests (avoids config validation errors)
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test_token")
os.environ.setdefault("DISCORD_DIGEST_CHANNEL_ID", "123456789")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with -m 'not slow')")
    config.addinivalue_line("markers", "integration: marks tests that make real network calls")
