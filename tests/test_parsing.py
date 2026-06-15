import pytest

from twi_epub.errors import LockedChapterError
from twi_epub.parsing import SINGLE_CHAPTER_PARSE_OPTIONS, parse_chapter, parse_toc


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
          <p>——</p>
          <p>—But this is story text.</p>
          <p><a href="/table-of-contents/">Back to TOC</a></p>
          <hr />
          <p><a href="/previous/">Previous Chapter</a> <a href="/next/">Next Chapter</a></p>
          <p><strong>Author’s Note:</strong> This should be stripped.</p>
          <p>Fanart and credits should be stripped too.</p>
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
	assert "<hr" in chapter.html
	assert "***" in chapter.markdown
	assert "---" not in chapter.markdown
	assert "—But this is story text." in chapter.markdown
	assert "https://wanderinginn.com/table-of-contents/" in chapter.markdown
	assert "Previous Chapter" not in chapter.markdown
	assert "Next Chapter" not in chapter.markdown
	assert "Author’s Note" not in chapter.markdown
	assert "Fanart and credits" not in chapter.markdown
	assert "No gallery found" not in chapter.markdown
	assert "script" not in chapter.html


def test_parse_chapter_detects_locked_page():
	html = """
    <html><head><title>Locked</title></head>
    <body>This content is password protected. Log in with Patreon.</body></html>
    """

	with pytest.raises(LockedChapterError):
		parse_chapter(html, "https://wanderinginn.com/locked/")


def test_single_chapter_parse_keeps_author_notes_and_manual_cleanup_text():
	chapter = parse_chapter(
		_chapter_html(
			"7.02",
			"""
			<p>Real chapter text.</p>
			<p>(A young woman from the Phillipines is a [Fisher] at the end of the world.
			The Last Tide, a comicbook illustrated by Shane Sandulak will be coming out this
			summer! Click on this link for more details!)</p>
			<p><strong>Author's Note:</strong> This should remain.</p>
			<p>More notes.</p>
			<p><a href="/previous/">Previous Chapter</a></p>
			""",
		),
		"https://wanderinginn.com/2020/01/26/7-02/",
		options=SINGLE_CHAPTER_PARSE_OPTIONS,
	)

	assert "Real chapter text." in chapter.markdown
	assert "The Last Tide" in chapter.markdown
	assert "Author's Note" in chapter.markdown
	assert "More notes." in chapter.markdown
	assert "Previous Chapter" not in chapter.markdown


def test_parse_chapter_normalizes_stylized_unicode_text_but_not_attributes():
	chapter = parse_chapter(
		_chapter_html(
			"𝟏𝟎.𝟔𝟕 𝐎",
			"""
			<p>𝔗𝔥𝔢 𝐈𝐧𝐧 has ＦＵＬＬＷＩＤＴＨ text and a ﬁne café.</p>
			<p><a href="https://example.com/𝔗𝔥𝔢">𝓛𝓲𝓷𝓴</a></p>
			""",
		),
		"https://wanderinginn.com/2026/06/14/10-67-o/",
		options=SINGLE_CHAPTER_PARSE_OPTIONS,
	)

	assert chapter.title == "10.67 O"
	assert "The Inn has FULLWIDTH text and a fine café." in chapter.markdown
	assert "[Link](https://example.com/𝔗𝔥𝔢)" in chapter.markdown
	assert "𝔗𝔥𝔢" in chapter.html


def test_parse_chapter_marks_recoverable_and_literal_redactions():
	chapter = parse_chapter(
		_chapter_html(
			"7.25",
			"""
			<p>The raider was <span style="opacity: 0">Lady Example</span>.</p>
			<p><span class="spoiler">Another identity</span> was hidden.</p>
			<p>There were ███ raiders and █████ names.</p>
			<p><span style="color: #ff0000">Ordinary red text</span></p>
			<pre>Keep ███ as written here.</pre>
			""",
		),
		"https://wanderinginn.com/2020/05/27/7-25/",
		options=SINGLE_CHAPTER_PARSE_OPTIONS,
	)

	assert "[Redacted in original: Lady Example]" in chapter.markdown
	assert "[Redacted in original: Another identity]" in chapter.markdown
	assert "There were [redacted] raiders and [redacted] names." in chapter.markdown
	assert '<span style="color: #ff0000">Ordinary red text</span>' in chapter.markdown
	assert "Keep ███ as written here." in chapter.markdown


def test_parse_chapter_removes_volume_seven_podcast_notice():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - The Innkeeper's [Knight]",
			"""
			<p>Real chapter text.</p>
			<p>(A podcast talking about The Last Tide is out, featuring one of our Discord moderators,
			Blue Juice! Check it out <a href="https://example.com">here</a>!)</p>
			""",
		),
		"https://wanderinginn.com/2020/10/18/interlude-the-innkeepers-knight/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "podcast talking about The Last Tide" not in chapter.markdown


def test_parse_chapter_removes_volume_seven_last_tide_notice():
	chapter = parse_chapter(
		_chapter_html(
			"7.02",
			"""
			<p>Real chapter text.</p>
			<p>(A young woman from the Phillipines is a [Fisher] at the end of the world.
			The Last Tide, a comicbook illustrated by Shane Sandulak will be coming out this
			summer! Click on this <a href="https://example.com">link</a> for more details!)</p>
			""",
		),
		"https://wanderinginn.com/2020/01/26/7-02/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "young woman from the Phillipines" not in chapter.markdown
	assert "The Last Tide" not in chapter.markdown


def test_parse_chapter_removes_volume_seven_amazon_notice():
	for title in ("7.50", "7.56"):
		chapter = parse_chapter(
			_chapter_html(
				title,
				"""
				<p>Real chapter text.</p>
				<p>(The Wandering Inn, Volume 3 – Part 1 is up on <a href="https://example.com">Amazon</a>!
				Check it out and consider
				leaving a review—the audiobook should begin recording in January, 2021!)</p>
				""",
			),
			f"https://wanderinginn.com/2020/10/18/{title.replace('.', '-')}/",
		)

		assert "Real chapter text." in chapter.markdown
		assert "Volume 3" not in chapter.markdown
		assert "audiobook should begin recording" not in chapter.markdown


def test_parse_chapter_removes_solstice_reader_instruction():
	chapter = parse_chapter(
		_chapter_html(
			"7.61",
			"""
			<p>Real chapter text.</p>
			<p>(Before going to next chapter, read Solstice Pt. 4-9. This is for users who do not
			see hyperlinks, such as those on mobile devices or WordPress’ Reader Mode.)</p>
			""",
		),
		"https://wanderinginn.com/2020/12/20/solstice-pt-3/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "Before going to next chapter" not in chapter.markdown


def test_parse_chapter_unlinks_final_solstice_chapter_link_only():
	chapter = parse_chapter(
		_chapter_html(
			"7.61",
			"""
			<p><a href="/2020/12/20/solstice-pt-2/">Earlier Solstice reference</a>.</p>
			<p>More story.</p>
			<p>More story still.</p>
			<p>She reached the <a href="/2020/12/20/solstice-pt-4/">door</a>.</p>
			""",
		),
		"https://wanderinginn.com/2020/12/20/solstice-pt-3/",
	)

	assert "[Earlier Solstice reference]" in chapter.markdown
	assert "https://wanderinginn.com/2020/12/20/solstice-pt-2/" in chapter.markdown
	assert "She reached the door." in chapter.markdown
	assert "https://wanderinginn.com/2020/12/20/solstice-pt-4/" not in chapter.markdown
	assert (
		'<a href="https://wanderinginn.com/2020/12/20/solstice-pt-4/">door</a>' not in chapter.html
	)


def _chapter_html(title: str, body: str) -> str:
	return f"""
	<html>
	  <head><meta property="og:title" content="{title}" /></head>
	  <body>
	    <article class="twi-article">
	      {body}
	    </article>
	  </body>
	</html>
	"""
