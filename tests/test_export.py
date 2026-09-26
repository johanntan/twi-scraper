from bs4 import BeautifulSoup
from ebooklib import epub

from twi_scraper.export import (
	chapter_markdown_filename,
	write_chapter_markdown,
	write_epub,
	write_markdown,
)
from twi_scraper.models import Chapter, Volume


def test_write_markdown_and_epub(tmp_path):
	volume = Volume(number=3, title="Volume 3")
	chapters = [
		Chapter(
			title="3.00",
			url="https://wanderinginn.com/2017/07/01/3-00/",
			html="<div><p>Hello <em>Innworld</em>.</p></div>",
			markdown="Hello *Innworld*.",
			published_at="2017-07-01T00:00:00+00:00",
		)
	]

	md_path = tmp_path / "twi-volume-03.md"
	epub_path = tmp_path / "twi-volume-03.epub"

	write_markdown(volume, chapters, md_path)
	write_epub(volume, chapters, epub_path)

	markdown = md_path.read_text(encoding="utf-8")
	assert "# The Wandering Inn - Volume 3" in markdown
	assert "## [3.00](https://wanderinginn.com/2017/07/01/3-00/)" in markdown
	assert "Source:" not in markdown
	assert "Published:" not in markdown
	assert epub_path.exists()

	book = epub.read_epub(str(epub_path))
	assert book.get_metadata("DC", "title")[0][0] == "The Wandering Inn - Volume 3"
	assert [book.get_item_with_id(item_id).file_name for item_id, _ in book.spine] == [
		"001-3-00.xhtml"
	]
	chapter_items = [item for item in book.get_items() if item.file_name.endswith(".xhtml")]
	chapter_html = chapter_items[0].get_content().decode("utf-8")
	assert '<h1><a href="https://wanderinginn.com/2017/07/01/3-00/">3.00</a></h1>' in chapter_html
	assert "Source chapter" not in chapter_html
	assert "Published:" not in chapter_html


def test_write_single_chapter_markdown(tmp_path):
	chapter = Chapter(
		title="10.67 O",
		url="https://wanderinginn.com/2026/06/14/10-67-o/",
		html="<div><p>Hello.</p></div>",
		markdown="Hello.\n\n***\n\nAuthor's Note.",
	)
	path = tmp_path / chapter_markdown_filename(chapter.title)

	write_chapter_markdown(chapter, path)

	assert path.name == "TWI-10.67-O.md"
	assert path.read_text(encoding="utf-8") == (
		"# [10.67 O](https://wanderinginn.com/2026/06/14/10-67-o/)\n\n"
		"Hello.\n\n***\n\nAuthor's Note.\n"
	)


def test_all_renderers_normalize_accessible_unicode(tmp_path):
	volume = Volume(number=10, title="Volume 10")
	chapter = Chapter(
		title="𝟏𝟎.𝟔𝟔 𝐎",
		url="https://wanderinginn.com/2026/06/07/10-66-o/",
		html=(
			'<div><p>𝔗𝔥𝔢 𝐈𝐧𝐧 hid <span style="opacity: 0">a secret</span> and ███.</p>'
			'<a href="https://example.com/𝔗𝔥𝔢">𝓛𝓲𝓷𝓴</a></div>'
		),
		markdown=(
			"𝔗𝔥𝔢 𝐈𝐧𝐧 and [𝓛𝓲𝓷𝓴](https://example.com/𝔗𝔥𝔢) hid "
			'<span style="opacity: 0">a secret</span> and ███.'
		),
	)
	chapter_path = tmp_path / chapter_markdown_filename(chapter.title)
	volume_path = tmp_path / "twi-volume-10.md"
	epub_path = tmp_path / "twi-volume-10.epub"

	write_chapter_markdown(chapter, chapter_path)
	write_markdown(volume, [chapter], volume_path)
	write_epub(volume, [chapter], epub_path)

	assert chapter_path.name == "TWI-10.66-O.md"
	assert "The Inn and [Link](https://example.com/𝔗𝔥𝔢)" in chapter_path.read_text(encoding="utf-8")
	assert "[Redacted in original: a secret] and [redacted]." in chapter_path.read_text(
		encoding="utf-8"
	)
	assert "## [10.66 O]" in volume_path.read_text(encoding="utf-8")

	book = epub.read_epub(str(epub_path))
	item = next(item for item in book.get_items() if item.file_name == "001-10-66-o.xhtml")
	html = item.get_content().decode("utf-8")
	visible_text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
	assert ">10.66 O</a></h1>" in html
	assert "The Inn" in html
	assert "[Redacted in original: a secret] and [redacted]." in visible_text
	assert ">Link</a>" in html
	assert 'href="https://example.com/𝔗𝔥𝔢"' in html
