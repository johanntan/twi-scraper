from twi_epub.downloader import parse_format_spec, parse_volume_spec


def test_parse_volume_spec():
	assert parse_volume_spec("1-3,5") == [1, 2, 3, 5]


def test_parse_format_spec():
	assert parse_format_spec("epub,markdown") == {"epub", "md"}
