"""API Client for Is Around."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

import aiofiles
import aiohttp
from aiohttp import ClientResponseError

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def handle_401(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T | None]]:
    """Decorator to handle 401 Unauthorized errors."""

    @wraps(func)
    async def wrapper(self: "IsAroundConnector", *args: Any, **kwargs: Any) -> T | None:
        """Wrap the function."""
        try:
            return await func(self, *args, **kwargs)
        except ClientResponseError as e:
            if e.status == 401:
                _LOGGER.debug("Got 401, re-authenticating")
                if not self._username or not self._password:
                    _LOGGER.error("Cannot re-authenticate, no credentials stored")
                    raise e

                authenticated = await self.authenticate(self._username, self._password)
                if authenticated:
                    _LOGGER.debug(
                        "Re-authentication successful, retrying original call"
                    )
                    return await func(self, *args, **kwargs)

                _LOGGER.error("Re-authentication failed")
                raise e

            raise e

    return wrapper


class IsAroundConnector:
    """Connector for Is Around API."""

    def __init__(self, session: aiohttp.ClientSession, app_url: str) -> None:
        """Initialize the connector."""
        self._session = session
        self._app_url = app_url.rstrip("/")
        self._token: str | None = None
        self._cookies: dict[str, str] = {}
        self._username: str | None = None
        self._password: str | None = None

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with the API."""
        self._username = username
        self._password = password

        url = f"{self._app_url}/api/admin/login"
        payload = {"username": username, "password": password}

        try:
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    # Capture cookies
                    for cookie in response.cookies:
                        self._cookies[cookie] = response.cookies[cookie].value
                    return True

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

    @handle_401
    async def get_observances(self) -> dict[str, Any]:
        """Get next observances."""
        url = f"{self._app_url}/api/admin/attendance/observances"
        # Use cookies if available
        async with self._session.get(url, cookies=self._cookies) as response:
            response.raise_for_status()
            return await response.json()

    @handle_401
    async def download_pdf(self, date: str, output_path: str) -> None:
        """Download PDF for a specific date."""
        url = f"{self._app_url}/api/admin/attendance/{date}/export-pdf"
        payload = {"service": "all"}
        async with self._session.post(
            url, json=payload, cookies=self._cookies
        ) as response:
            response.raise_for_status()
            async with aiofiles.open(output_path, mode="wb") as f:
                await f.write(await response.read())

    @handle_401
    async def send_attendance_push(self) -> dict[str, Any]:
        """Send attendance push message."""
        url = f"{self._app_url}/api/admin/candidates/service-attendance/send"
        async with self._session.post(
            url, json={"dummy": ""}, cookies=self._cookies
        ) as response:
            response.raise_for_status()
            return await response.json()

    @handle_401
    async def get_attendance_stats(self, date: str) -> dict[str, Any]:
        """Get attendance stats for a specific date."""
        url = f"{self._app_url}/api/admin/attendance/{date}"
        async with self._session.get(url, cookies=self._cookies) as response:
            response.raise_for_status()
            return await response.json()

    def discard_session(self) -> None:
        """Discard current session (cookies)."""
        self._cookies = {}
        _LOGGER.debug("Session cookies discarded")

    async def build_session(self) -> bool:
        """Build a new session by authenticating."""
        if not self._username or not self._password:
            _LOGGER.error("Cannot build session, no credentials stored")
            return False
        return await self.authenticate(self._username, self._password)
