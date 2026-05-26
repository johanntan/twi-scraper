from __future__ import annotations

import json
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from pathlib import Path

import browser_cookie3
import httpx

SUPPORTED_BROWSERS = ("chrome", "firefox", "safari", "edge")


def load_browser_cookies(browser: str) -> CookieJar:
	browser = browser.lower()
	loaders = {
		"chrome": browser_cookie3.chrome,
		"firefox": browser_cookie3.firefox,
		"safari": browser_cookie3.safari,
		"edge": browser_cookie3.edge,
	}
	if browser not in loaders:
		supported = ", ".join(SUPPORTED_BROWSERS)
		raise ValueError(f"Unsupported browser {browser!r}. Use one of: {supported}.")

	return loaders[browser](domain_name="wanderinginn.com")


def load_cookie_file(path: Path) -> CookieJar:
	text = path.read_text(encoding="utf-8").lstrip()
	if text.startswith("[") or text.startswith("{"):
		return _load_json_cookie_file(text)

	jar = MozillaCookieJar(str(path))
	jar.load(ignore_discard=True, ignore_expires=True)
	return jar


def apply_cookie_jar(client: httpx.Client, jar: CookieJar) -> None:
	for cookie in jar:
		client.cookies.set(
			cookie.name,
			cookie.value,
			domain=cookie.domain,
			path=cookie.path,
		)


def _load_json_cookie_file(text: str) -> CookieJar:
	raw = json.loads(text)
	if isinstance(raw, dict):
		raw = raw.get("cookies", [])
	if not isinstance(raw, list):
		raise ValueError("JSON cookies must be a list or an object with a 'cookies' list.")

	jar = CookieJar()
	for item in raw:
		if not isinstance(item, dict):
			continue
		name = str(item.get("name") or "")
		value = str(item.get("value") or "")
		domain = str(item.get("domain") or ".wanderinginn.com")
		if not name:
			continue
		jar.set_cookie(
			Cookie(
				version=0,
				name=name,
				value=value,
				port=None,
				port_specified=False,
				domain=domain,
				domain_specified=True,
				domain_initial_dot=domain.startswith("."),
				path=str(item.get("path") or "/"),
				path_specified=True,
				secure=bool(item.get("secure", True)),
				expires=_int_or_none(item.get("expires") or item.get("expirationDate")),
				discard=False,
				comment=None,
				comment_url=None,
				rest={"HttpOnly": bool(item.get("httpOnly", False))},
				rfc2109=False,
			)
		)
	return jar


def _int_or_none(value: object) -> int | None:
	if value is None:
		return None
	try:
		return int(float(value))
	except (TypeError, ValueError):
		return None
