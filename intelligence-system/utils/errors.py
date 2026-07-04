"""
Custom exception hierarchy for the intelligence system.
"""

from __future__ import annotations


class IntelligenceError(Exception):
    """Base class for all system errors."""


class ProviderError(IntelligenceError):
    """Raised when a data provider fails to fetch or parse."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ConfigurationError(IntelligenceError):
    """Raised for invalid or missing configuration."""


class DeliveryError(IntelligenceError):
    """Raised when Discord delivery fails."""


class ProcessingError(IntelligenceError):
    """Raised during aggregation, deduplication, or ranking."""
