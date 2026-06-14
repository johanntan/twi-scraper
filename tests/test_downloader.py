import pytest

from twi_epub.catalog import VOLUME_URL_OVERRIDES, apply_volume_overrides
from twi_epub.downloader import (
	CACHE_VERSION,
	_load_cached_chapter,
	_write_cached_chapter,
	parse_format_spec,
	parse_volume_spec,
	resolve_chapter_from_volumes,
	resolve_chapter_selector,
)
from twi_epub.errors import ParseError
from twi_epub.models import Chapter, ChapterLink, Volume


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
		path.read_text(encoding="utf-8").replace(
			f'"cache_version": {CACHE_VERSION}', '"cache_version": 1'
		)
	)

	assert _load_cached_chapter(tmp_path, 3, 1, chapter.url) is None


def test_volume_one_and_two_overrides_have_expected_counts():
	assert len(VOLUME_URL_OVERRIDES[1]) == 66
	assert len(VOLUME_URL_OVERRIDES[2]) == 57
	assert VOLUME_URL_OVERRIDES[1][0] == "https://wanderinginn.com/2017/03/03/rw1-00/"
	assert VOLUME_URL_OVERRIDES[1][-1] == "https://wanderinginn.com/2017/03/04/rw1-63/"
	assert VOLUME_URL_OVERRIDES[2][0] == "https://wanderinginn.com/2017/03/07/interlude-2/"
	assert VOLUME_URL_OVERRIDES[2][-1] == "https://wanderinginn.com/2017/07/29/2-41/"


def test_apply_volume_overrides_preserves_known_titles():
	volumes = {
		1: Volume(
			number=1,
			title="Volume 1",
			chapters=(
				ChapterLink(title="1.00", url="https://wanderinginn.com/2017/03/03/rw1-00/"),
			),
		),
		3: Volume(number=3, title="Volume 3"),
	}

	updated = apply_volume_overrides(volumes)

	assert len(updated[1].chapters) == 66
	assert updated[1].chapters[0].title == "1.00"
	assert updated[3] is volumes[3]


def test_resolve_chapter_selector_supports_latest_titles_and_rewrite_aliases():
	volumes = {
		1: Volume(
			number=1,
			title="Volume 1",
			chapters=(
				ChapterLink(
					title="Rw1 05",
					url="https://wanderinginn.com/2017/03/03/rw1-05/",
				),
			),
		),
		10: Volume(
			number=10,
			title="Volume 10",
			chapters=(
				ChapterLink(
					title="10.66 (Pt. 1)",
					url="https://wanderinginn.com/2026/05/31/10-66-pt-1/",
				),
				ChapterLink(
					title="10.66 (Pt. 2)",
					url="https://wanderinginn.com/2026/06/07/10-66-pt-2/",
				),
			),
		),
	}

	assert resolve_chapter_from_volumes("1.05", volumes).url.endswith("/rw1-05/")
	assert resolve_chapter_from_volumes("10.66（Pt. 2）", volumes).url.endswith("/10-66-pt-2/")
	assert resolve_chapter_from_volumes("latest", volumes).title == "10.66 (Pt. 2)"


def test_resolve_chapter_selector_rejects_ambiguous_titles():
	volumes = {
		3: Volume(
			number=3,
			title="Volume 3",
			chapters=(
				ChapterLink(title="Interlude", url="https://wanderinginn.com/2017/07/01/one/"),
			),
		),
		4: Volume(
			number=4,
			title="Volume 4",
			chapters=(
				ChapterLink(title="Interlude", url="https://wanderinginn.com/2018/01/01/two/"),
			),
		),
	}

	with pytest.raises(ParseError, match="ambiguous"):
		resolve_chapter_from_volumes("interlude", volumes)


def test_resolve_chapter_selector_accepts_only_wandering_inn_urls():
	url = "https://wanderinginn.com/2026/06/07/10-66-pt-2/"

	assert resolve_chapter_selector(object(), url).url == url
	with pytest.raises(ParseError, match="wanderinginn.com"):
		resolve_chapter_selector(object(), "https://example.com/chapter/")
