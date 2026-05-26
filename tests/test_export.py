from ebooklib import epub

from twi_epub.export import write_epub, write_markdown
from twi_epub.models import Chapter, Volume


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

	md_path = tmp_path / "volume-03.md"
	epub_path = tmp_path / "volume-03.epub"

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
	chapter_items = [item for item in book.get_items() if item.file_name.endswith(".xhtml")]
	chapter_html = chapter_items[0].get_content().decode("utf-8")
	assert '<h1><a href="https://wanderinginn.com/2017/07/01/3-00/">3.00</a></h1>' in chapter_html
	assert "Source chapter" not in chapter_html
	assert "Published:" not in chapter_html
