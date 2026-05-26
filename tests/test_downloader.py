from twi_epub.downloader import (
	_load_cached_chapter,
	_write_cached_chapter,
	parse_format_spec,
	parse_volume_spec,
)
from twi_epub.models import Chapter


def test_parse_volume_spec():
	assert parse_volume_spec("1-3,5") == [1, 2, 3, 5]


def test_parse_format_spec():
	assert parse_format_spec("epub,markdown") == {"epub", "md"}


def test_cache_rejects_old_version(tmp_path):
	chapter = Chapter(
		title="3.00",
		url="https://wanderinginn.com/2017/07/01/3-00/",
		html="<div><p>Hello.</p></div>",
		markdown="Hello.",
	)
	_write_cached_chapter(tmp_path, 3, 1, chapter)
	path = next((tmp_path / ".cache" / "volume-03").glob("*.json"))
	path.write_text(
		path.read_text(encoding="utf-8").replace('"cache_version": 2', '"cache_version": 1')
	)

	assert _load_cached_chapter(tmp_path, 3, 1, chapter.url) is None
