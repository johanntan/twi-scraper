from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from . import __version__
from .auth import apply_cookie_jar, load_browser_cookies, load_cookie_file

USER_AGENT = (
	f"twi-scraper/{__version__} (personal archive tool; +https://github.com/johanntan/twi-scraper)"
)
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class RateLimitedClient(httpx.Client):
	"""HTTP client with polite pacing and bounded retries for transient failures."""

	def __init__(
		self,
		*args: object,
		request_interval: float = 1.0,
		max_attempts: int = 4,
		sleep: Callable[[float], None] = time.sleep,
		monotonic: Callable[[], float] = time.monotonic,
		**kwargs: object,
	) -> None:
		super().__init__(*args, **kwargs)
		if request_interval < 0:
			raise ValueError("request_interval cannot be negative.")
		if max_attempts < 1:
			raise ValueError("max_attempts must be at least 1.")
		self.request_interval = request_interval
		self.max_attempts = max_attempts
		self._sleep = sleep
		self._monotonic = monotonic
		self._last_request_started: float | None = None

	def get(self, url: httpx.URL | str, **kwargs: object) -> httpx.Response:
		for attempt in range(1, self.max_attempts + 1):
			self._wait_for_request_slot()
			try:
				response = super().get(url, **kwargs)
			except httpx.TransportError:
				if attempt == self.max_attempts:
					raise
				self._sleep(_exponential_backoff(attempt))
				continue

			if response.status_code not in RETRYABLE_STATUS_CODES or attempt == self.max_attempts:
				return response

			delay = _retry_delay(response, attempt)
			response.close()
			self._sleep(delay)

		raise RuntimeError("Request retry loop ended unexpectedly.")

	def post(self, url: httpx.URL | str, **kwargs: object) -> httpx.Response:
		self._wait_for_request_slot()
		return super().post(url, **kwargs)

	def _wait_for_request_slot(self) -> None:
		now = self._monotonic()
		if self._last_request_started is not None:
			remaining = self.request_interval - (now - self._last_request_started)
			if remaining > 0:
				self._sleep(remaining)
				now = self._monotonic()
		self._last_request_started = now


def build_client(
	*,
	browser: str | None = None,
	cookies_file: Path | None = None,
	timeout: float = 30.0,
) -> RateLimitedClient:
	client = RateLimitedClient(
		follow_redirects=True,
		timeout=timeout,
		headers={
			"User-Agent": USER_AGENT,
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		},
	)

	if browser:
		apply_cookie_jar(client, load_browser_cookies(browser))
	if cookies_file:
		apply_cookie_jar(client, load_cookie_file(cookies_file))

	return client


def fetch_text(client: httpx.Client, url: str) -> str:
	response = client.get(url)
	response.raise_for_status()
	return response.text


def _retry_delay(response: httpx.Response, attempt: int) -> float:
	retry_after = response.headers.get("Retry-After")
	if retry_after:
		try:
			return min(max(float(retry_after), 0.0), 60.0)
		except ValueError:
			try:
				retry_at = parsedate_to_datetime(retry_after)
				if retry_at.tzinfo is None:
					retry_at = retry_at.replace(tzinfo=UTC)
				delay = (retry_at - datetime.now(UTC)).total_seconds()
				return min(max(delay, 0.0), 60.0)
			except (TypeError, ValueError, OverflowError):
				pass
	return _exponential_backoff(attempt)


def _exponential_backoff(attempt: int) -> float:
	return min(float(2 ** (attempt - 1)), 30.0)
