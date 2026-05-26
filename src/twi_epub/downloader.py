from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .errors import LockedChapterError, ParseError
from .export import write_epub, write_markdown
from .http import fetch_text
from .models import Chapter, Volume
from .parsing import TOC_URL, manifest_dump, parse_chapter, parse_toc


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
	toc_html = fetch_text(client, TOC_URL)
	volumes = parse_toc(toc_html)
	missing = [number for number in volume_numbers if number not in volumes]
	if missing:
		available = ", ".join(str(number) for number in sorted(volumes))
		raise ParseError(
			f"Volume(s) not found: {', '.join(map(str, missing))}. Available: {available}"
		)
	return [volumes[number] for number in volume_numbers]


def download_volume(
	client: httpx.Client,
	volume: Volume,
	*,
	output_dir: Path,
	formats: set[str],
	refresh: bool = False,
) -> list[Path]:
	chapters: list[Chapter] = []
	manifest: list[dict[str, object]] = []

	for index, link in enumerate(volume.chapters, start=1):
		chapter = _load_cached_chapter(output_dir, volume.number, index, link.url)
		if chapter is None or refresh:
			html = fetch_text(client, link.url)
			chapter = parse_chapter(html, link.url)
			_write_cached_chapter(output_dir, volume.number, index, chapter)
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
	stem = f"volume-{volume.number:02d}"
	if "md" in formats:
		path = output_dir / f"{stem}.md"
		write_markdown(volume, chapters, path)
		paths.append(path)
	if "epub" in formats:
		path = output_dir / f"{stem}.epub"
		write_epub(volume, chapters, path)
		paths.append(path)

	_manifest_path(output_dir, volume.number).write_text(
		manifest_dump(
			{
				"volume": volume.number,
				"title": volume.title,
				"generated_at": datetime.now(timezone.utc).isoformat(),
				"formats": sorted(formats),
				"chapters": manifest,
			}
		),
		encoding="utf-8",
	)
	return paths


def _load_cached_chapter(output_dir: Path, volume: int, index: int, url: str) -> Chapter | None:
	path = _chapter_cache_path(output_dir, volume, index, url)
	if not path.exists():
		return None
	data = json.loads(path.read_text(encoding="utf-8"))
	return Chapter(
		title=str(data["title"]),
		url=str(data["url"]),
		html=str(data["html"]),
		markdown=str(data["markdown"]),
		published_at=data.get("published_at"),
	)


def _write_cached_chapter(output_dir: Path, volume: int, index: int, chapter: Chapter) -> None:
	path = _chapter_cache_path(output_dir, volume, index, chapter.url)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		manifest_dump(
			{
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


def _chapter_cache_path(output_dir: Path, volume: int, index: int, url: str) -> Path:
	digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
	return output_dir / ".cache" / f"volume-{volume:02d}" / f"{index:03d}-{digest}.json"


def _manifest_path(output_dir: Path, volume: int) -> Path:
	path = output_dir / ".cache" / f"volume-{volume:02d}" / "manifest.json"
	path.parent.mkdir(parents=True, exist_ok=True)
	return path


def auth_hint(error: Exception, browser: str | None) -> str:
	if isinstance(error, LockedChapterError):
		attempted = f" using {browser} cookies" if browser else ""
		return (
			f"{error}{attempted}. Log in to wanderinginn.com/Patreon in that browser "
			"or pass --cookies-file with exported authorized cookies."
		)
	return str(error)
