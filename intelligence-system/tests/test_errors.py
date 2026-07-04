"""Tests for utils/errors.py — custom exception hierarchy."""

from __future__ import annotations

import pytest
from utils.errors import (
    IntelligenceError,
    ProviderError,
    ConfigurationError,
    DeliveryError,
    ProcessingError,
)


class TestExceptionHierarchy:
    def test_provider_error_is_intelligence_error(self):
        assert issubclass(ProviderError, IntelligenceError)

    def test_configuration_error_is_intelligence_error(self):
        assert issubclass(ConfigurationError, IntelligenceError)

    def test_delivery_error_is_intelligence_error(self):
        assert issubclass(DeliveryError, IntelligenceError)

    def test_processing_error_is_intelligence_error(self):
        assert issubclass(ProcessingError, IntelligenceError)

    def test_intelligence_error_is_exception(self):
        assert issubclass(IntelligenceError, Exception)


class TestProviderError:
    def test_message_includes_provider_name(self):
        err = ProviderError("rss", "connection refused")
        assert "rss" in str(err)
        assert "connection refused" in str(err)

    def test_provider_attribute_set(self):
        err = ProviderError("github", "404 not found")
        assert err.provider == "github"

    def test_formatted_message(self):
        err = ProviderError("reddit", "timeout")
        assert str(err) == "[reddit] timeout"

    def test_catchable_as_intelligence_error(self):
        with pytest.raises(IntelligenceError):
            raise ProviderError("test", "boom")

    def test_catchable_as_base_exception(self):
        with pytest.raises(Exception):
            raise ProviderError("test", "boom")


class TestConfigurationError:
    def test_basic_raise(self):
        with pytest.raises(ConfigurationError, match="missing token"):
            raise ConfigurationError("missing token")

    def test_catchable_as_intelligence_error(self):
        with pytest.raises(IntelligenceError):
            raise ConfigurationError("bad config")


class TestDeliveryError:
    def test_basic_raise(self):
        with pytest.raises(DeliveryError):
            raise DeliveryError("channel not found")


class TestProcessingError:
    def test_basic_raise(self):
        with pytest.raises(ProcessingError):
            raise ProcessingError("dedup failed")

    def test_catchable_as_intelligence_error(self):
        with pytest.raises(IntelligenceError):
            raise ProcessingError("rank failed")
