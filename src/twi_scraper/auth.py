"""Load authorized Wandering Inn cookies without persisting their values."""

from __future__ import annotations

import json
from collections.abc import Callable
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from pathlib import Path
from urllib.parse import urljoin, urlparse

import browser_cookie3
import httpx
from bs4 import BeautifulSoup, Tag

from .errors import LockedChapterError

SUPPORTED_BROWSERS = ("chrome", "firefox", "safari", "edge")
ALLOWED_HOSTS = frozenset({"wanderinginn.com", "www.wanderinginn.com"})


def submit_chapter_password(
	client: httpx.Client, url: str, html: str, password_provider: Callable[[], str]
) -> None:
	"""Submit a protected chapter's own password form in the current session."""
	soup = BeautifulSoup(html, "lxml")
	form = next(
		(
			form
			for form in soup.find_all("form")
			if isinstance(form, Tag) and form.select_one('input[name="post_password"]')
		),
		None,
	)
	if form is not None:
		if str(form.get("method", "post")).lower() != "post":
			raise LockedChapterError("The chapter password form does not use POST.")
		action = urljoin(url, str(form.get("action") or url))
		fields = {
			str(field.get("name")): str(field.get("value") or "")
			for field in form.select('input[type="hidden"][name]')
		}
		password_field = "post_password"
	elif _has_hybrid_password_gate(soup):
		action = url
		fields = {}
		password_field = "hybrid_pass"
	else:
		raise LockedChapterError("The locked chapter has no supported password form.")

	parsed = urlparse(action)
	if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username:
		raise LockedChapterError("The chapter password form points to an unsafe address.")

	password = password_provider()
	if not password:
		raise LockedChapterError(f"No chapter password was provided for {url}.")
	fields[password_field] = password
	response = client.post(action, data=fields, follow_redirects=False)
	if response.is_error:
		response.raise_for_status()


def _has_hybrid_password_gate(soup: BeautifulSoup) -> bool:
	if "patreon exclusive" not in soup.get_text(" ", strip=True).casefold():
		return False
	return any(
		"hybrid-password-form" in script.get_text() and 'name="hybrid_pass"' in script.get_text()
		for script in soup.find_all("script")
	)


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
	if text.startswith(("[", "{")):
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
		raise TypeError("JSON cookies must be a list or an object with a 'cookies' list.")

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
