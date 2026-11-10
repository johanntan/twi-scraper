"""Fetching from wanderinginn.com: table of contents, chapters, unlocking."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .model import norm_url

BASE = "https://wanderinginn.com"
TOC_URL = f"{BASE}/table-of-contents/"
ARCHIVE_URL = f"{BASE}/vol-1-archive/"
WP_POSTPASS_URL = f"{BASE}/wp-login.php?action=postpass&wpe-login=true"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 twi-downloader/0.1"
)
INDEX_TTL = 60 * 60  # seconds the table of contents / archive list stay cached

# Single books that live outside the table of contents.
BOOKS = {
    "griefman": {
        "title": "Griefman",
        "start": f"{BASE}/2024/09/14/griefman-pt-1/",
        "slug_prefix": "griefman-",
    },
}

EXTRA_TITLES = re.compile(r"^tales of innworld|crossover comic|^announcement\b", re.I)


class SiteError(Exception):
    pass


class SiteBlocked(SiteError):
    """The site's firewall blocked this connection (seen after wrong password attempts)."""


@dataclass
class ChapterRef:
    title: str
    url: str
    volume: str | None = None

    @property
    def is_extra(self) -> bool:
        """Image-only or non-story posts (Tales of Innworld etc.)."""
        return bool(EXTRA_TITLES.search(self.title))


@dataclass
class Volume:
    key: str  # "1".."10" or "archive"
    title: str
    chapters: list[ChapterRef] = field(default_factory=list)


@dataclass
class Page:
    url: str
    title: str
    content_html: str
    lock: str | None = None  # None, "patreon" or "wp"
    next_url: str | None = None
    bad_password: bool = False
    tier: str | None = None  # Patreon tier named on the lock screen; passwords go by tier

    @property
    def lock_key(self) -> str:
        """Which password a locked page needs: same key, same password."""
        if self.lock == "patreon":
            return f"patreon:{self.tier or '?'}"
        return f"wp:{self.url}"


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(Path.home(), ".cache")
    return Path(base) / "twi"


class Site:
    def __init__(self, cache_dir: Path | None = None, refresh: bool = False, delay: float = 1.0):
        self.cache_dir = cache_dir or default_cache_dir()
        self.refresh = refresh
        self.delay = delay
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._toc: list[Volume] | None = None

    # --- HTTP -------------------------------------------------------------

    def _wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.monotonic()

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        for attempt in range(3):
            self._wait()
            try:
                r = self.session.request(method, url, timeout=60, **kw)
            except requests.RequestException as e:
                if attempt == 2:
                    raise SiteError(f"could not reach {url}: {e}") from e
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 404:
                raise SiteError(f"page not found: {url}")
            if r.status_code == 403 and "Firewall" in r.text:
                raise SiteBlocked(
                    "the site's firewall has blocked this connection from locked pages "
                    "(it reacts to wrong password attempts). Other pages still work. "
                    "Wait a while, then try again with the right password."
                )
            if r.status_code >= 400:
                raise SiteError(f"{url} returned HTTP {r.status_code}")
            r.encoding = "utf-8"
            return r
        raise SiteError(f"giving up on {url}")

    # --- cache ------------------------------------------------------------

    def _cache_path(self, kind: str, url: str) -> Path:
        h = hashlib.sha1(url.encode()).hexdigest()[:20]
        return self.cache_dir / kind / f"{h}.json"

    def _cache_get(self, kind: str, url: str, ttl: float | None = None) -> dict | None:
        if self.refresh:
            return None
        p = self._cache_path(kind, url)
        try:
            if ttl is not None and time.time() - p.stat().st_mtime > ttl:
                return None
            return json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def _cache_put(self, kind: str, url: str, data: dict) -> None:
        p = self._cache_path(kind, url)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
            tmp.replace(p)
        except OSError:
            pass

    def _index_html(self, url: str) -> str:
        cached = self._cache_get("index", url, ttl=INDEX_TTL)
        if cached:
            return cached["html"]
        html = self._request("GET", url).text
        self._cache_put("index", url, {"html": html})
        return html

    # --- table of contents --------------------------------------------------

    def volumes(self) -> list[Volume]:
        if self._toc is None:
            self._toc = parse_toc(self._index_html(TOC_URL))
            if not self._toc:
                raise SiteError("could not read the table of contents (site layout changed?)")
        return self._toc

    def volume(self, key: str) -> Volume:
        key = key.lower().removeprefix("vol").removeprefix("ume").strip(" -")
        if key in ("archive", "1-archive", "a"):
            return self.archive()
        for v in self.volumes():
            if v.key == key:
                return v
        keys = ", ".join([v.key for v in self.volumes()] + ["archive"])
        raise SiteError(f"no volume {key!r}; available: {keys}")

    def archive(self) -> Volume:
        return parse_archive(self._index_html(ARCHIVE_URL))

    def all_chapters(self) -> list[ChapterRef]:
        return [c for v in self.volumes() for c in v.chapters]

    def find_by_url(self, url: str) -> ChapterRef | None:
        n = norm_url(url)
        for c in self.all_chapters():
            if norm_url(c.url) == n:
                return c
        return None

    def find_by_title(self, query: str) -> list[ChapterRef]:
        q = _norm_title(query)
        chapters = self.all_chapters()
        exact = [c for c in chapters if _norm_title(c.title) == q]
        if exact:
            return exact
        return [c for c in chapters if _norm_title(c.title).startswith(q + " ")]

    # --- pages --------------------------------------------------------------

    def fetch(self, url: str) -> Page:
        """Fetch a chapter page. The result may be locked (page.lock is set)."""
        url = norm_url(url) or url
        cached = self._cache_get("pages", url)
        if cached:
            return Page(**cached)
        page = parse_page(url, self._request("GET", url).text)
        self._store(page)
        return page

    def _store(self, page: Page) -> None:
        if page.lock is None:
            self._cache_put("pages", page.url, {
                "url": page.url, "title": page.title,
                "content_html": page.content_html, "next_url": page.next_url,
            })

    def _fresh(self, url: str) -> Page:
        # Cache-busting query: the site's CDN otherwise serves the locked copy.
        r = self._request("GET", url, params={"nc": str(random.randint(1, 10**9))})
        return parse_page(url, r.text)

    def unlock(self, page: Page, password: str) -> Page | None:
        """Try one password. Returns the unlocked page, or None if it was wrong."""
        if page.lock == "patreon":
            r = self._request("POST", page.url, data={"hybrid_pass": password},
                              headers={"Referer": page.url, "Origin": BASE})
            result = parse_page(page.url, r.text)
            if result.lock and not result.bad_password:
                result = self._fresh(page.url)
        elif page.lock == "wp":
            self._request("POST", WP_POSTPASS_URL,
                          data={"post_password": password, "Submit": "Submit"},
                          headers={"Referer": page.url, "Origin": BASE})
            result = self._fresh(page.url)
        else:
            return page
        if result.lock:
            return None
        self._store(result)
        return result


# --- parsing ------------------------------------------------------------------


def _norm_title(t: str) -> str:
    t = t.lower().replace(" ", " ")
    t = re.sub(r"[‐-―\-]", " ", t)
    t = re.sub(r"\bpt\.?\s*", "pt ", t)
    t = re.sub(r"[()\[\]:,#]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_toc(html: str) -> list[Volume]:
    soup = BeautifulSoup(html, "lxml")
    vols: list[Volume] = []
    for wrap in soup.select("div.volume-wrapper"):
        vid = wrap.get("id", "")
        key = vid.removeprefix("vol-") if vid.startswith("vol-") else str(len(vols) + 1)
        h = wrap.select_one(".volume-title")
        vol = Volume(key=key, title=h.get_text(" ", strip=True) if h else f"Volume {key}")
        seen: set[str] = set()
        for a in wrap.select("div.chapter-entry .body-web a[href]"):
            url = norm_url(a["href"])
            if not url or url in seen:
                continue
            seen.add(url)
            vol.chapters.append(ChapterRef(a.get_text(" ", strip=True), url, key))
        vols.append(vol)
    return vols


DATED = re.compile(r"^https://wanderinginn\.com/\d{4}/\d{2}/\d{2}/[^/]+/$")


def parse_archive(html: str) -> Volume:
    soup = BeautifulSoup(html, "lxml")
    content = _content_container(soup) or soup
    vol = Volume(key="archive", title="Volume 1 (Archive)")
    seen: set[str] = set()
    for a in content.find_all("a", href=True):
        url = norm_url(a["href"])
        if not url or not DATED.match(url) or "/rw" in url or url in seen:
            continue
        seen.add(url)
        vol.chapters.append(ChapterRef(a.get_text(" ", strip=True), url, "archive"))
    if not vol.chapters:
        raise SiteError("could not read the Volume 1 archive page (site layout changed?)")
    return vol


def _content_container(soup: BeautifulSoup):
    w = soup.select_one('[data-widget_type="theme-post-content.default"]')
    if w is None:
        return None
    return w.select_one(".elementor-widget-container") or w


def parse_page(url: str, html: str) -> Page:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else url
    title = re.sub(r"\s*[-–—|]\s*The Wandering Inn\s*$", "", title).strip() or url
    bad = bool(re.search(r'HYBRID_BAD_PASSWORD\s*=\s*"1"', html))
    container = _content_container(soup)
    article = soup.find("article", class_="twi-article")
    gate = container.select_one(".patreon-protected-post") if container is not None else None
    if gate is not None and article is None:
        m = re.search(r"Minimum tier:\s*(.+?)\s+or higher", gate.get_text(" ", strip=True))
        return Page(url, title, "", lock="patreon", bad_password=bad, tier=m.group(1) if m else None)
    if container is not None and container.find("input", attrs={"name": "post_password"}):
        return Page(url, title, "", lock="wp")
    body = article if article is not None else container
    if body is None:
        raise SiteError(f"could not find the chapter text on {url} (site layout changed?)")
    next_url = None
    for a in body.find_all("a", href=True):
        if re.search(r"next\s+chapter", a.get_text(" ", strip=True), re.I):
            next_url = norm_url(a["href"])
    return Page(url, title, str(body), next_url=next_url)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
