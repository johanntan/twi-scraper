"""Resolve, download, cache, and export Wandering Inn chapters."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from .catalog import apply_volume_download_exclusions, apply_volume_overrides
from .errors import LockedChapterError, ParseError
from .export import chapter_markdown_filename, write_chapter_markdown, write_epub, write_markdown
from .http import fetch_text
from .models import Chapter, ChapterLink, Volume
from .parsing import (
	DEFAULT_CHAPTER_PARSE_OPTIONS,
	SINGLE_CHAPTER_PARSE_OPTIONS,
	TOC_URL,
	ChapterParseOptions,
	manifest_dump,
	parse_chapter,
	parse_toc,
)

CACHE_VERSION = 10


def parse_volume_spec(spec: str) -> list[int]:
	values: set[int] = set()
	for part in spec.split(","):
		part = part.strip()
		if not part:
			continue
		if "-" in part:
			start_text, end_text = part.split("-", 1)
			start = int(start_text)
			end = int(end_text)
			if end < start:
				raise ValueError(f"Invalid descending volume range: {part}")
			values.update(range(start, end + 1))
		else:
			values.add(int(part))

	if not values:
		raise ValueError("At least one volume is required.")
	return sorted(values)


def parse_format_spec(spec: str) -> set[str]:
	values = {part.strip().lower() for part in spec.split(",") if part.strip()}
	invalid = values - {"md", "markdown", "epub"}
	if invalid:
		raise ValueError(f"Unsupported format(s): {', '.join(sorted(invalid))}")
	if "markdown" in values:
		values.add("md")
		values.remove("markdown")
	return values or {"md", "epub"}


def load_selected_volumes(client: httpx.Client, volume_numbers: list[int]) -> list[Volume]:
	volumes = load_volume_catalog(client)
	missing = [number for number in volume_numbers if number not in volumes]
	if missing:
		available = ", ".join(str(number) for number in sorted(volumes))
		raise ParseError(
			f"Volume(s) not found: {', '.join(map(str, missing))}. Available: {available}"
		)
	return [apply_volume_download_exclusions(volumes[number]) for number in volume_numbers]


def load_volume_catalog(client: httpx.Client) -> dict[int, Volume]:
	toc_html = fetch_text(client, TOC_URL)
	return apply_volume_overrides(parse_toc(toc_html))


def resolve_chapter_selector(client: httpx.Client, selector: str) -> ChapterLink:
	direct_url = _validated_chapter_url(selector)
	if direct_url is not None:
		return ChapterLink(title=selector, url=direct_url)
	return resolve_chapter_from_volumes(selector, load_volume_catalog(client))


def resolve_chapter_from_volumes(selector: str, volumes: dict[int, Volume]) -> ChapterLink:
	if selector.strip().casefold() == "latest":
		for number in sorted(volumes, reverse=True):
			if volumes[number].chapters:
				return volumes[number].chapters[-1]
		raise ParseError("No chapters were found in the table of contents.")

	selector_key = _normalize_chapter_selector(selector)
	matches: dict[str, ChapterLink] = {}
	for volume in volumes.values():
		for chapter in volume.chapters:
			if selector_key in _chapter_aliases(chapter):
				matches[chapter.url] = chapter

	if not matches:
		raise ParseError(
			f"Chapter title not found: {selector}. Try the exact table-of-contents title "
			"or pass the chapter URL."
		)
	if len(matches) > 1:
		candidates = "\n".join(f"- {chapter.title}: {chapter.url}" for chapter in matches.values())
		raise ParseError(f"Chapter title is ambiguous: {selector}\n{candidates}")
	return next(iter(matches.values()))


def download_single_chapter(
	client: httpx.Client,
	link: ChapterLink,
	*,
	output_dir: Path,
) -> Path:
	chapter = fetch_chapter(client, link.url, options=SINGLE_CHAPTER_PARSE_OPTIONS)
	path = output_dir / chapter_markdown_filename(chapter.title)
	write_chapter_markdown(chapter, path)
	return path


def download_volume(
	client: httpx.Client,
	volume: Volume,
	*,
	output_dir: Path,
	cache_dir: Path,
	formats: set[str],
	refresh: bool = False,
) -> list[Path]:
	chapters: list[Chapter] = []
	manifest: list[dict[str, object]] = []

	for index, link in enumerate(volume.chapters, start=1):
		chapter = _load_cached_chapter(cache_dir, volume.number, index, link.url)
		if chapter is None or refresh:
			chapter = fetch_chapter(client, link.url)
			_write_cached_chapter(cache_dir, volume.number, index, chapter)
			status = "downloaded"
		else:
			status = "cached"

		chapters.append(chapter)
		manifest.append(
			{
				"index": index,
				"title": chapter.title,
				"url": chapter.url,
				"status": status,
				"published_at": chapter.published_at,
			}
		)

	paths: list[Path] = []
	stem = f"twi-volume-{volume.number:02d}"
	if "md" in formats:
		path = output_dir / f"{stem}.md"
		write_markdown(volume, chapters, path)
		paths.append(path)
	if "epub" in formats:
		path = output_dir / f"{stem}.epub"
		write_epub(volume, chapters, path)
		paths.append(path)

	_manifest_path(cache_dir, volume.number).write_text(
		manifest_dump(
			{
				"volume": volume.number,
				"cache_version": CACHE_VERSION,
				"title": volume.title,
				"generated_at": datetime.now(timezone.utc).isoformat(),
				"formats": sorted(formats),
				"chapters": manifest,
			}
		),
		encoding="utf-8",
	)
	return paths


def fetch_chapter(
	client: httpx.Client,
	url: str,
	*,
	options: ChapterParseOptions = DEFAULT_CHAPTER_PARSE_OPTIONS,
) -> Chapter:
	html = fetch_text(client, url)
	return parse_chapter(html, url, options=options)


def _validated_chapter_url(selector: str) -> str | None:
	value = selector.strip()
	parsed = urlparse(value)
	if not parsed.scheme and not parsed.netloc:
		return None
	if parsed.scheme not in {"http", "https"}:
		raise ParseError("Chapter URL must use http or https.")
	if parsed.hostname not in {"wanderinginn.com", "www.wanderinginn.com"}:
		raise ParseError("Chapter URL must be on wanderinginn.com.")
	return value


def _chapter_aliases(chapter: ChapterLink) -> set[str]:
	aliases = {_normalize_chapter_selector(chapter.title)}
	slug = unquote(urlparse(chapter.url).path.rstrip("/").rsplit("/", 1)[-1])

	rewrite_match = re.fullmatch(r"rw(\d+)-(\d+)(?:-([a-z]))?", slug, re.IGNORECASE)
	if rewrite_match:
		volume, number, suffix = rewrite_match.groups()
		aliases.add(_normalize_chapter_selector(f"{volume}.{number}"))
		if suffix:
			aliases.add(_normalize_chapter_selector(f"{volume}.{number} {suffix}"))

	numeric_match = re.fullmatch(r"(\d+)-(\d+)(?:-(.+))?", slug, re.IGNORECASE)
	if numeric_match:
		volume, number, suffix = numeric_match.groups()
		aliases.add(_normalize_chapter_selector(f"{volume}.{number}"))
		if suffix:
			parts = suffix.split("-")
			aliases.add(_normalize_chapter_selector(".".join((volume, number, *parts))))
			aliases.add(_normalize_chapter_selector(f"{volume}.{number} {' '.join(parts)}"))
			if len(parts) == 2 and parts[0].casefold() == "pt":
				aliases.add(_normalize_chapter_selector(f"{volume}.{number} (Pt. {parts[1]})"))

	return aliases


def _normalize_chapter_selector(value: str) -> str:
	value = unicodedata.normalize("NFKC", value)
	value = re.sub(r"[‐‑‒–—―]", "-", value)
	value = re.sub(r"\s+", " ", value).strip().casefold()
	value = re.sub(r"\s*([.()\[\]-])\s*", r"\1", value)
	if re.fullmatch(r"\d+(?:[._-]\d+)+(?:[a-z])?", value):
		value = value.replace("_", ".").replace("-", ".")
	return value


def _load_cached_chapter(cache_dir: Path, volume: int, index: int, url: str) -> Chapter | None:
	path = _chapter_cache_path(cache_dir, volume, index, url)
	if not path.exists():
		return None
	data = json.loads(path.read_text(encoding="utf-8"))
	if data.get("cache_version") != CACHE_VERSION:
		return None
	return Chapter(
		title=str(data["title"]),
		url=str(data["url"]),
		html=str(data["html"]),
		markdown=str(data["markdown"]),
		published_at=data.get("published_at"),
	)


def _write_cached_chapter(cache_dir: Path, volume: int, index: int, chapter: Chapter) -> None:
	path = _chapter_cache_path(cache_dir, volume, index, chapter.url)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		manifest_dump(
			{
				"cache_version": CACHE_VERSION,
				"title": chapter.title,
				"url": chapter.url,
				"published_at": chapter.published_at,
				"html": chapter.html,
				"markdown": chapter.markdown,
				"cached_at": datetime.now(timezone.utc).isoformat(),
			}
		),
		encoding="utf-8",
	)


def _chapter_cache_path(cache_dir: Path, volume: int, index: int, url: str) -> Path:
	digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
	return cache_dir / f"volume-{volume:02d}" / f"{index:03d}-{digest}.json"


def _manifest_path(cache_dir: Path, volume: int) -> Path:
	path = cache_dir / f"volume-{volume:02d}" / "manifest.json"
	path.parent.mkdir(parents=True, exist_ok=True)
	return path


def auth_hint(error: Exception, browser: str | None) -> str:
	if isinstance(error, LockedChapterError):
		attempted = f" using {browser} cookies" if browser else ""
		return (
			f"{error}{attempted}. Try logging in with Firefox and running with --browser firefox, "
			"or pass --cookies-file with exported authorized cookies."
		)
	return str(error)
