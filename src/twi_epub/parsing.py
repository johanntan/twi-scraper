from __future__ import annotations

import json
import re
from html import escape
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .errors import LockedChapterError, ParseError
from .models import Chapter, ChapterLink, Volume

BASE_URL = "https://wanderinginn.com/"
TOC_URL = "https://wanderinginn.com/table-of-contents/"


def parse_toc(html: str, base_url: str = TOC_URL) -> dict[int, Volume]:
	soup = BeautifulSoup(html, "lxml")
	volumes: dict[int, Volume] = {}

	for wrapper in soup.select("div.volume-wrapper"):
		heading = wrapper.select_one(".volume-header .volume-title") or wrapper.select_one(
			".volume-title"
		)
		if heading is None:
			continue

		title = _clean_text(heading.get_text(" ", strip=True))
		match = re.search(r"\bVolume\s+(\d+)\b", title, re.IGNORECASE)
		if match is None:
			continue

		number = int(match.group(1))
		chapters: list[ChapterLink] = []
		seen_urls: set[str] = set()

		for entry in wrapper.select(".chapter-entry"):
			link = entry.select_one(".body-web a[href]") or entry.find("a", href=True)
			if not isinstance(link, Tag):
				continue
			href = str(link.get("href", "")).strip()
			label = _clean_text(link.get_text(" ", strip=True))
			if not href or not label:
				continue

			url = urljoin(base_url, href)
			if url in seen_urls:
				continue
			seen_urls.add(url)

			book = entry.find_parent(class_="book-wrapper")
			book_title = None
			if isinstance(book, Tag):
				book_title = str(book.get("data-book-title") or "").strip() or None

			chapters.append(
				ChapterLink(
					title=label,
					url=url,
					book_title=book_title,
					audiobook_label=_cell_text(entry, ".body-audiobook"),
					ebook_label=_cell_text(entry, ".body-ebook"),
				)
			)

		volumes[number] = Volume(number=number, title=title, chapters=tuple(chapters))

	if not volumes:
		raise ParseError("No volume wrappers were found in the table of contents.")

	return volumes


def parse_chapter(html: str, url: str) -> Chapter:
	soup = BeautifulSoup(html, "lxml")
	if is_locked_page(soup):
		raise LockedChapterError(f"Chapter appears to be locked: {url}")

	title = _chapter_title(soup)
	published_at = _meta_content(soup, "article:published_time")
	article = _chapter_article(soup)

	_remove_noise(article)
	normalized_html = _normalize_article_html(article)
	markdown = _markdown_from_html(normalized_html)

	if not markdown:
		raise ParseError(f"No readable chapter text found at {url}")

	return Chapter(
		title=title,
		url=url,
		html=normalized_html,
		markdown=markdown,
		published_at=published_at,
	)


def is_locked_page(soup: BeautifulSoup) -> bool:
	text = soup.get_text(" ", strip=True).lower()
	title = _chapter_title(soup).lower()

	markers = (
		"this content is password protected",
		"enter your password to view comments",
		"patreon exclusive",
		"log in with patreon",
		"unlock this post",
		"you must be logged in",
	)
	if any(marker in text for marker in markers):
		return True

	has_article = soup.select_one("article.twi-article, #main-content article, .entry-content")
	patreon_gate = "patreongate" in text or "patreon gate" in text
	return has_article is None and patreon_gate and "patreon" in title + text


def _chapter_article(soup: BeautifulSoup) -> Tag:
	selectors = (
		"article.twi-article",
		"#main-content article",
		"#reader-content article",
		".elementor-widget-theme-post-content .elementor-widget-container",
		".entry-content",
		"article .post-content",
	)
	candidates = [node for selector in selectors for node in soup.select(selector)]
	candidates = [node for node in candidates if isinstance(node, Tag)]
	if not candidates:
		raise ParseError("Could not find the chapter content container.")

	return max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))


def _chapter_title(soup: BeautifulSoup) -> str:
	for key in ("og:title", "twitter:title"):
		value = _meta_content(soup, key)
		if value:
			return _clean_text(value.removesuffix(" - The Wandering Inn"))

	heading = soup.select_one("h1, h2.elementor-heading-title, .entry-title")
	if heading:
		return _clean_text(heading.get_text(" ", strip=True))

	title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled Chapter"
	return _clean_text(title.removesuffix(" - The Wandering Inn"))


def _meta_content(soup: BeautifulSoup, key: str) -> str | None:
	node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
	if isinstance(node, Tag):
		value = str(node.get("content") or "").strip()
		if value:
			return value
	return None


def _cell_text(root: Tag, selector: str) -> str | None:
	node = root.select_one(selector)
	if node is None:
		return None
	value = _clean_text(node.get_text(" ", strip=True))
	return value or None


def _clean_text(value: str) -> str:
	return re.sub(r"\s+", " ", value).strip()


def _remove_noise(article: Tag) -> None:
	selectors = (
		"script",
		"style",
		"noscript",
		"form",
		"iframe",
		".sharedaddy",
		".jp-relatedposts",
		".post-likes-widget",
		".navigation",
		".nav-links",
		".non-article",
	)
	for node in article.select(", ".join(selectors)):
		node.decompose()


def _normalize_article_html(article: Tag) -> str:
	for link in article.find_all("a", href=True):
		link["href"] = urljoin(BASE_URL, str(link["href"]))

	for img in article.find_all("img", src=True):
		img["src"] = urljoin(BASE_URL, str(img["src"]))
		for attr in ("srcset", "sizes", "loading", "decoding"):
			img.attrs.pop(attr, None)

	body = BeautifulSoup("", "lxml").new_tag("div")
	for child in list(article.children):
		body.append(child.extract())
	return str(body)


def manifest_dump(data: object) -> str:
	return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _markdown_from_html(html: str) -> str:
	return (
		_TwiMarkdownConverter(
			heading_style="ATX",
			bullets="-",
			strip=["script", "style"],
		)
		.convert(html)
		.strip()
	)


class _TwiMarkdownConverter(MarkdownConverter):
	def convert_span(self, el: Tag, text: str, parent_tags: set[str]) -> str:
		return self._inline_html_if_styled(el, text, {"style", "class", "title"})

	def convert_font(self, el: Tag, text: str, parent_tags: set[str]) -> str:
		return self._inline_html_if_styled(el, text, {"style", "class", "color", "face"})

	def _inline_html_if_styled(self, el: Tag, text: str, attrs: set[str]) -> str:
		kept_attrs = []
		for name in attrs:
			if name not in el.attrs:
				continue
			value = el.attrs[name]
			if isinstance(value, list):
				value = " ".join(str(item) for item in value)
			kept_attrs.append(f'{name}="{escape(str(value), quote=True)}"')

		if not kept_attrs:
			return text
		return f"<{el.name} {' '.join(sorted(kept_attrs))}>{text}</{el.name}>"
