"""API Client for Is Around."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import aiofiles

_LOGGER = logging.getLogger(__name__)

class IsAroundConnector:
    """Connector for Is Around API."""

    def __init__(self, session: aiohttp.ClientSession, app_url: str) -> None:
        """Initialize the connector."""
        self._session = session
        self._app_url = app_url.rstrip("/")
        self._token: str | None = None
        self._cookies: dict[str, str] = {}

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with the API."""
        url = f"{self._app_url}/api/admin/login"
        payload = {"username": username, "password": password}
        
        try:
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    # Capture cookies
                    for cookie in response.cookies:
                        self._cookies[cookie] = response.cookies[cookie].value
                    return True
                else:
                    _LOGGER.error("Authentication failed: %s", response.status)
                    return False
        except Exception as e:
            _LOGGER.exception("Error during authentication: %s", e)
            return False

    async def test_connection(self) -> bool:
        """Test connection to the API (without auth first)."""
        url = f"{self._app_url}/api/admin/attendance/observances"
        try:
            async with self._session.get(url) as response:
                # If 401/403, it means we can reach the server but need auth.
                # If 200, maybe no auth needed?
                if response.status in (200, 401, 403):
                    return True
                return False
        except Exception:
            return False

    async def get_observances(self) -> dict[str, Any]:
        """Get next observances."""
        url = f"{self._app_url}/api/admin/attendance/observances"
        # Use cookies if available
        async with self._session.get(url, cookies=self._cookies) as response:
            response.raise_for_status()
            return await response.json()

    async def download_pdf(self, date: str, output_path: str) -> None:
        """Download PDF for a specific date."""
        url = f"{self._app_url}/api/admin/attendance/{date}/export-pdf"
        payload = {"service": "all"}
        async with self._session.post(url, json=payload, cookies=self._cookies) as response:
            response.raise_for_status()
            async with aiofiles.open(output_path, mode="wb") as f:
                await f.write(await response.read())
