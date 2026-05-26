from twi_epub.catalog import VOLUME_URL_OVERRIDES, apply_volume_overrides
from twi_epub.downloader import (
	_load_cached_chapter,
	_write_cached_chapter,
	parse_format_spec,
	parse_volume_spec,
)
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
		path.read_text(encoding="utf-8").replace('"cache_version": 2', '"cache_version": 1')
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
