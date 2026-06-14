from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag


def normalize_accessible_text(value: str) -> str:
	return unicodedata.normalize("NFKC", value)


def normalize_accessible_markdown(markdown: str) -> str:
	protected: list[str] = []

	def protect(match: re.Match[str]) -> str:
		protected.append(match.group(0))
		return f"\x00TWI-PROTECTED-{len(protected) - 1}\x00"

	value = re.sub(r"(?i)\b(?:href|src)\s*=\s*([\"']).*?\1", protect, markdown)
	value = re.sub(r"(?<=\]\()[^)\n]+(?=\))", protect, value)
	value = re.sub(r"https?://[^\s<]+", protect, value)
	value = normalize_accessible_text(value)

	for index, original in enumerate(protected):
		value = value.replace(f"\x00TWI-PROTECTED-{index}\x00", original)
	return value


def normalize_accessible_html(html: str) -> str:
	soup = BeautifulSoup(html, "lxml")
	root = soup.body or soup
	_normalize_text_nodes(root)

	if soup.body is None:
		return str(soup)
	return "".join(str(child) for child in soup.body.children)


def normalize_tag_text(root: Tag) -> None:
	_normalize_text_nodes(root)


def _normalize_text_nodes(root: Tag) -> None:
	for node in list(root.find_all(string=True)):
		if not isinstance(node, NavigableString):
			continue
		normalized = normalize_accessible_text(str(node))
		if normalized != str(node):
			node.replace_with(normalized)
