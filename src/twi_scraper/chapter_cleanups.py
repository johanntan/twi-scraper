"""Targeted cleanup rules for known chapter-specific notices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import Tag

BASE_URL = "https://wanderinginn.com/"


@dataclass(frozen=True)
class ParagraphRemovalRule:
	text: str
	titles: frozenset[str] = frozenset()


PARAGRAPH_REMOVALS: tuple[ParagraphRemovalRule, ...] = (
	ParagraphRemovalRule(
		text=(
			"(A podcast talking about The Last Tide is out, featuring one of our Discord "
			"moderators, Blue Juice! Check it out here!)"
		),
		titles=frozenset({"interlude - the innkeeper's [knight]"}),
	),
	ParagraphRemovalRule(
		text=(
			"(A young woman from the Philippines is a [Fisher] at the end of the world. The "
			"Last Tide, a comicbook illustrated by Shane Sandulak will be coming out this "
			"summer! Click on this link for more details!)"
		),
		titles=frozenset({"7.02"}),
	),
	ParagraphRemovalRule(
		text=(
			"(The Wandering Inn, Volume 3 - Part 1 is up on Amazon! Check it out and "
			"consider leaving a review-the audiobook should begin recording in January, 2021!)"
		),
		titles=frozenset({"7.50", "7.56"}),
	),
	ParagraphRemovalRule(
		text=(
			"(Before going to next chapter, read Solstice Pt. 4-9. This is for users who do "
			"not see hyperlinks, such as those on mobile devices or WordPress' Reader Mode.)"
		),
	),
)


def apply_manual_chapter_cleanups(article: Tag, *, title: str, url: str) -> None:
	normalized_title = _normalize_text(title).lower()
	_remove_matching_paragraphs(article, normalized_title)
	_unlink_solstice_next_chapter_links(article, normalized_title, url)


def _remove_matching_paragraphs(article: Tag, normalized_title: str) -> None:
	for node in list(article.find_all(["p", "div", "section"])):
		if not isinstance(node, Tag):
			continue
		text = _normalize_text(node.get_text(" ", strip=True))
		for rule in PARAGRAPH_REMOVALS:
			if rule.titles and normalized_title not in rule.titles:
				continue
			if text == _normalize_text(rule.text):
				node.decompose()
				break


def _unlink_solstice_next_chapter_links(article: Tag, normalized_title: str, url: str) -> None:
	current_is_solstice = _looks_solstice(f"{normalized_title} {url}")
	for node in _final_paragraphs(article, count=3):
		for link in list(node.find_all("a", href=True)):
			href = str(link.get("href") or "")
			if not _is_wandering_inn_chapter_link(href):
				continue
			if current_is_solstice or _looks_solstice(href):
				link.unwrap()


def _final_paragraphs(article: Tag, *, count: int) -> list[Tag]:
	nodes = [
		node
		for node in article.find_all(["p", "div"], recursive=False)
		if isinstance(node, Tag) and _normalize_text(node.get_text(" ", strip=True))
	]
	return nodes[-count:]


def _is_wandering_inn_chapter_link(href: str) -> bool:
	url = urljoin(BASE_URL, href)
	parsed = urlparse(url)
	host = parsed.netloc.lower()
	if host not in {"wanderinginn.com", "www.wanderinginn.com"}:
		return False
	return bool(re.fullmatch(r"/20\d{2}/\d{2}/\d{2}/[^/]+/?", parsed.path))


def _looks_solstice(value: str) -> bool:
	return "solstice" in value.lower()


def _normalize_text(value: str) -> str:
	text = (
		re.sub(r"\s+", " ", value)
		.replace("\u2013", "-")
		.replace("\u2014", "-")
		.replace("\u2018", "'")
		.replace("\u2019", "'")
		.replace("Phillipines", "Philippines")
		.strip()
	)
	return re.sub(r"\s+([!?,.;:)])", r"\1", text)
