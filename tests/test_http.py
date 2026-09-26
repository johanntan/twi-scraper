from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from twi_scraper.http import RateLimitedClient


class FakeClock:
	def __init__(self) -> None:
		self.now = 0.0
		self.sleeps: list[float] = []

	def monotonic(self) -> float:
		return self.now

	def sleep(self, seconds: float) -> None:
		self.sleeps.append(seconds)
		self.now += seconds


def _client(
	handler: Callable[[httpx.Request], httpx.Response],
	clock: FakeClock,
	**kwargs: object,
) -> RateLimitedClient:
	return RateLimitedClient(
		transport=httpx.MockTransport(handler),
		sleep=clock.sleep,
		monotonic=clock.monotonic,
		**kwargs,
	)


def test_client_waits_between_requests() -> None:
	clock = FakeClock()
	with _client(lambda request: httpx.Response(200, request=request), clock) as client:
		client.get("https://wanderinginn.com/one/")
		client.get("https://wanderinginn.com/two/")

	assert clock.sleeps == [1.0]


def test_client_paces_password_submission_without_retry() -> None:
	clock = FakeClock()
	attempts = []

	def handler(request: httpx.Request) -> httpx.Response:
		attempts.append(request.method)
		return httpx.Response(503 if request.method == "POST" else 200, request=request)

	with _client(handler, clock) as client:
		client.get("https://wanderinginn.com/chapter/")
		response = client.post("https://wanderinginn.com/wp-login.php", data={"post_password": "x"})

	assert response.status_code == 503
	assert attempts == ["GET", "POST"]
	assert clock.sleeps == [1.0]


def test_client_retries_retry_after_response() -> None:
	clock = FakeClock()
	statuses = iter((429, 200))

	def handler(request: httpx.Request) -> httpx.Response:
		status = next(statuses)
		headers = {"Retry-After": "3"} if status == 429 else {}
		return httpx.Response(status, headers=headers, request=request)

	with _client(handler, clock) as client:
		response = client.get("https://wanderinginn.com/chapter/")

	assert response.status_code == 200
	assert clock.sleeps == [3.0]


def test_client_uses_bounded_exponential_backoff() -> None:
	clock = FakeClock()
	attempts = 0

	def handler(request: httpx.Request) -> httpx.Response:
		nonlocal attempts
		attempts += 1
		return httpx.Response(503, request=request)

	with _client(handler, clock, request_interval=0, max_attempts=3) as client:
		response = client.get("https://wanderinginn.com/chapter/")

	assert response.status_code == 503
	assert attempts == 3
	assert clock.sleeps == [1.0, 2.0]


def test_client_retries_transport_errors_then_raises() -> None:
	clock = FakeClock()

	def handler(request: httpx.Request) -> httpx.Response:
		raise httpx.ConnectError("network unavailable", request=request)

	with (
		_client(handler, clock, request_interval=0, max_attempts=2) as client,
		pytest.raises(httpx.ConnectError),
	):
		client.get("https://wanderinginn.com/chapter/")

	assert clock.sleeps == [1.0]
