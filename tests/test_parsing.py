import pytest

from twi_epub.errors import LockedChapterError
from twi_epub.parsing import parse_chapter, parse_toc


TOC_HTML = """
<div id="table-of-contents">
  <div id="vol-1" class="volume-wrapper">
    <div class="volume-header"><h2 class="volume-title">Volume 1</h2></div>
    <div class="book-wrapper" data-book-title="The Wandering Inn: Book One, Part One">
      <div class="chapter-entry table-row is-mobile" data-book-number="1">
        <div class="body-web table-cell"><a href="/2017/03/03/rw1-00/">1.00</a></div>
        <div class="body-audiobook table-cell">Chapter 1</div>
        <div class="body-ebook table-cell">1.00</div>
      </div>
      <div class="chapter-entry table-row is-mobile" data-book-number="1">
        <div class="body-web table-cell"><a href="https://wanderinginn.com/2017/03/03/rw1-01/">1.01</a></div>
        <div class="body-audiobook table-cell">Chapter 3</div>
        <div class="body-ebook table-cell">1.02</div>
      </div>
    </div>
  </div>
  <div id="vol-2" class="volume-wrapper">
    <div class="volume-header"><h2 class="volume-title">Volume 2</h2></div>
    <div class="book-wrapper" data-book-title="Fae and Fare">
      <div class="chapter-entry table-row is-mobile">
        <div class="body-web table-cell"><a href="/2017/04/01/2-00/">2.00</a></div>
      </div>
    </div>
  </div>
</div>
"""


CHAPTER_HTML = """
<html>
  <head>
    <meta property="og:title" content="9.33" />
    <meta property="article:published_time" content="2023-01-22T02:35:52+00:00" />
  </head>
  <body>
    <div id="reader-content">
      <main id="main-content">
        <article class="twi-article">
          <p>Then she was <em>there</em>.</p>
          <p><span style="color: #ff0000">Red text</span></p>
          <p><a href="/table-of-contents/">Back to TOC</a></p>
          <aside class="non-article">No gallery found.</aside>
          <script>ignored()</script>
        </article>
      </main>
    </div>
  </body>
</html>
"""


def test_parse_toc_groups_chapters_by_volume():
	volumes = parse_toc(TOC_HTML)

	assert sorted(volumes) == [1, 2]
	assert volumes[1].title == "Volume 1"
	assert [chapter.title for chapter in volumes[1].chapters] == ["1.00", "1.01"]
	assert volumes[1].chapters[0].url == "https://wanderinginn.com/2017/03/03/rw1-00/"
	assert volumes[1].chapters[0].book_title == "The Wandering Inn: Book One, Part One"
	assert volumes[1].chapters[0].audiobook_label == "Chapter 1"


def test_parse_chapter_extracts_article_and_metadata():
	chapter = parse_chapter(CHAPTER_HTML, "https://wanderinginn.com/2023/01/22/9-33/")

	assert chapter.title == "9.33"
	assert chapter.published_at == "2023-01-22T02:35:52+00:00"
	assert "Then she was *there*." in chapter.markdown
	assert '<span style="color: #ff0000">Red text</span>' in chapter.markdown
	assert "https://wanderinginn.com/table-of-contents/" in chapter.markdown
	assert "No gallery found" not in chapter.markdown
	assert "script" not in chapter.html


def test_parse_chapter_detects_locked_page():
	html = """
    <html><head><title>Locked</title></head>
    <body>This content is password protected. Log in with Patreon.</body></html>
    """

	with pytest.raises(LockedChapterError):
		parse_chapter(html, "https://wanderinginn.com/locked/")
