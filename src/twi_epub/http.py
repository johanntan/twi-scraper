from __future__ import annotations

from pathlib import Path

import httpx

from .auth import apply_cookie_jar, load_browser_cookies, load_cookie_file

USER_AGENT = "twi-epub/0.1 (+personal archive tool; https://wanderinginn.com/table-of-contents/)"


def build_client(
	*,
	browser: str | None = None,
	cookies_file: Path | None = None,
	timeout: float = 30.0,
) -> httpx.Client:
	client = httpx.Client(
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
