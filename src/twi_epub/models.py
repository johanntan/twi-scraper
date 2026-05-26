from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChapterLink:
	title: str
	url: str
	book_title: str | None = None
	audiobook_label: str | None = None
	ebook_label: str | None = None


@dataclass(frozen=True)
class Volume:
	number: int
	title: str
	chapters: tuple[ChapterLink, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Chapter:
	title: str
	url: str
	html: str
	markdown: str
	published_at: str | None = None
