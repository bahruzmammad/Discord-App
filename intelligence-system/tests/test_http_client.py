"""
Tests for utils/http_client.py — session management, rate limiting, and fetch helpers.

All network calls are mocked; no real HTTP requests are made.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_extracts_hostname(self):
        """_rate_limit must key on hostname, not full URL."""
        from utils.http_client import _rate_limit, _last_request, _RATE_LIMIT_SECONDS
        # Reset state
        _last_request.clear()

        url = "https://example.com/path?q=1"
        host = urlparse(url).netloc
        assert host == "example.com"

        # Should not raise
        await _rate_limit(url)
        assert host in _last_request

    @pytest.mark.asyncio
    async def test_different_hosts_tracked_independently(self):
        from utils.http_client import _rate_limit, _last_request
        _last_request.clear()

        await _rate_limit("https://host-a.com/x")
        await _rate_limit("https://host-b.com/y")

        assert "host-a.com" in _last_request
        assert "host-b.com" in _last_request


class TestSessionManagement:
    @pytest.mark.asyncio
    async def test_get_session_returns_session(self):
        from utils import http_client
        # Reset state
        http_client._session = None

        session = await http_client.get_session()
        assert session is not None
        await http_client.close_session()

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing(self):
        from utils import http_client
        http_client._session = None

        s1 = await http_client.get_session()
        s2 = await http_client.get_session()
        assert s1 is s2
        await http_client.close_session()

    @pytest.mark.asyncio
    async def test_close_session_sets_none(self):
        from utils import http_client
        http_client._session = None

        await http_client.get_session()
        await http_client.close_session()
        assert http_client._session is None

    @pytest.mark.asyncio
    async def test_close_session_idempotent(self):
        """Calling close_session twice must not raise."""
        from utils import http_client
        http_client._session = None
        await http_client.close_session()
        await http_client.close_session()


class TestFetchText:
    @pytest.mark.asyncio
    async def test_returns_text_on_200(self):
        from utils import http_client

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="<rss>content</rss>")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        result = await http_client.fetch_text("https://example.com/feed")
        assert result == "<rss>content</rss>"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        from utils import http_client

        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        result = await http_client.fetch_text("https://example.com/missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_after_all_retries_timeout(self):
        import aiohttp
        from utils import http_client

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        with patch("utils.http_client.asyncio.sleep", new_callable=AsyncMock):
            result = await http_client.fetch_text(
                "https://example.com/slow", retries=2, backoff=0.0
            )
        assert result is None


class TestFetchJson:
    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_200(self):
        from utils import http_client

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"key": "value"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        result = await http_client.fetch_json("https://api.example.com/data")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        from utils import http_client

        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        result = await http_client.fetch_json("https://api.example.com/fail")
        assert result is None

    @pytest.mark.asyncio
    async def test_passes_params_to_get(self):
        from utils import http_client

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[])
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        http_client._session = mock_session
        http_client._last_request.clear()

        params = {"page": "1", "limit": "10"}
        await http_client.fetch_json("https://api.example.com/list", params=params)
        mock_session.get.assert_called_once_with(
            "https://api.example.com/list", params=params
        )
