"""Async HTTP client for the SEC EDGAR API.

Single responsibility: make HTTP calls to EDGAR safely.
- Adds required headers (User-Agent)
- Enforces client-side rate limiting (stays under SEC's 10 req/sec)
- Retries transient failures with exponential backoff
- Logs every request with structured context

The class is an async context manager — use async with EdgarClient
to guarantee the connection pool gets closed cleanly
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, Self

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from finlab_research_assistant.core.config import settings
from finlab_research_assistant.core.logging import get_logger

log = get_logger(__name__)

class EdgarClient:
    """Async Edgar client with rate limts and retires"""
    def __init__(self, 
                user_agent: str | None = None,
                max_concurrent_requests: int | None = None, 
                timeout_seconds: float = 30.0
                ) -> None: 
                
                # allowed overwrite for testing, default to env config 
                self._user_agent = user_agent or settings.edgar_user_agent
                self._max_concurrent = ( max_concurrent_requests or settings.edgar_max_requests_per_second)
                
                # semaphore caps inflight request  
                self._semaphore = asyncio.Semaphore(self._max_concurrent)
                
                # create lzy httpx client
                self._client: httpx.AsyncClient | None = None 
                self._timeout = timeout_seconds 
                
    async def __aenter__(self) -> Self:
        """ Open HTTP Connection Pool"""
        self._client = httpx.AsyncClient(
            headers={
                # SEC Requirements: user agent
                "User-Agent": self._user_agent, 
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=self._timeout,
            follow_redirects=True,
        )
        log.debug("edgar_client.opened", max_concurrent=self._max_concurrent)
        return self
    
    async def __aexit__(self,
                    exc_type: type[BaseException] | None,
                    exc_val: BaseException | None,
                    exc_tb: TracebackType | None,
    ) -> None:
        """Close HTTP connection pool, runs even if exception was raised"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        log.debug("edgar_client.closed")
        
    @retry(
        # Retry up to 3 times on transient network issues or HTTP errors that
        retry=retry_if_exception_type(
            (httpx.RequestError, httpx.HTTPStatusError)
        ),
        stop=stop_after_attempt(3),
        # Exponential backoff and sleep
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,  # If all retries fail, raise the last exception
    )
    async def _request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Internal - perform a request with retry logic"""
        if self._client is None:
            raise RuntimeError(
                "EdgarClient must be used as async context manager"
            )

        # Semaphore acquisition is async-safe. If 8 requests are already
        # in flight, this `async with` blocks until one finishes
        async with self._semaphore:
            log.debug("edgar.request", method=method, url=url)
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

    async def get_json(self, url: str) -> dict[str, Any]:
        """get URL and parse the response as JSON. Returns parsed dict. Raises invalid JSON.
        """
        response = await self._request_with_retry("GET", url)
        return response.json()

    async def get_bytes(self, url: str) -> bytes:
        """get URL and return raw bytes"""
        response = await self._request_with_retry("GET", url)
        return response.content
