"""Render downloaded chapters as Markdown and EPUB files."""

from __future__ import annotations

import re
from pathlib import Path

from ebooklib import epub

from .models import Chapter, Volume
from .text import (
	normalize_accessible_html,
	normalize_accessible_markdown,
	normalize_accessible_text,
)


def slugify(value: str) -> str:
	slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
	return slug or "chapter"


def chapter_markdown_filename(title: str) -> str:
	title = normalize_accessible_text(title)
	safe_title = re.sub(r"[^a-zA-Z0-9.]+", "-", title).strip("-.")
	return f"TWI-{safe_title or 'chapter'}.md"


def write_chapter_markdown(chapter: Chapter, path: Path) -> None:
	title = normalize_accessible_text(chapter.title)
	markdown = normalize_accessible_markdown(chapter.markdown)
	content = "\n".join(
		[
			f"# [{_escape_markdown_link_text(title)}]({chapter.url})",
			"",
			markdown.strip(),
			"",
		]
	)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(content, encoding="utf-8")


def write_markdown(volume: Volume, chapters: list[Chapter], path: Path) -> None:
	lines = [
		f"# The Wandering Inn - Volume {volume.number}",
		"",
	]
	for chapter in chapters:
		title = normalize_accessible_text(chapter.title)
		markdown = normalize_accessible_markdown(chapter.markdown)
		lines.extend(
			[
				f"## [{_escape_markdown_link_text(title)}]({chapter.url})",
				"",
			]
		)
		lines.extend([markdown.strip(), ""])

	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_epub(volume: Volume, chapters: list[Chapter], path: Path) -> None:
	book = epub.EpubBook()
	book.set_identifier(f"twi-volume-{volume.number}")
	book.set_title(f"The Wandering Inn - Volume {volume.number}")
	book.set_language("en")
	book.add_author("pirateaba")
	book.add_metadata("DC", "source", "https://wanderinginn.com/table-of-contents/")

	epub_chapters: list[epub.EpubHtml] = []
	used_names: set[str] = set()
	for index, chapter in enumerate(chapters, start=1):
		title = normalize_accessible_text(chapter.title)
		basename = slugify(title)
		filename = f"{index:03d}-{basename}.xhtml"
		while filename in used_names:
			filename = f"{index:03d}-{basename}-{len(used_names)}.xhtml"
		used_names.add(filename)

		item = epub.EpubHtml(
			title=title,
			file_name=filename,
			lang="en",
		)
		item.content = _chapter_xhtml(chapter)
		book.add_item(item)
		epub_chapters.append(item)

	book.toc = tuple(epub_chapters)
	book.spine = epub_chapters
	book.add_item(epub.EpubNcx())
	book.add_item(epub.EpubNav())

	path.parent.mkdir(parents=True, exist_ok=True)
	epub.write_epub(str(path), book)


def _chapter_xhtml(chapter: Chapter) -> str:
	title = normalize_accessible_text(chapter.title)
	html = normalize_accessible_html(chapter.html)
	return f"""
<html>
  <head><title>{_escape(title)}</title></head>
  <body>
    <h1><a href="{_escape(chapter.url)}">{_escape(title)}</a></h1>
    {html}
  </body>
</html>
"""


def _escape(value: str) -> str:
	return (
		value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
	)


def _escape_markdown_link_text(value: str) -> str:
	return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
