import pytest

from twi_scraper.errors import LockedChapterError
from twi_scraper.parsing import SINGLE_CHAPTER_PARSE_OPTIONS, parse_chapter, parse_toc

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


def test_parse_chapter_uses_html_when_markdown_emphasis_boundaries_are_unsafe():
	chapter = parse_chapter(
		_chapter_html(
			"10.71 (Pt. 2)",
			"""
			<p><em>Keep the Rubirel Guard safe—</em>the armored Drakes hesitated,
			but everyone shouted at them to <em>run.</em></p>
			<p>This place is loaded<em>. </em>Wait, even <em>I’d</em> wear one.</p>
			<p>She thought <i>what—</i>then stopped.</p>
			""",
		),
		"https://wanderinginn.com/2026/07/22/10-71-pt-2/",
	)

	assert "<em>Keep the Rubirel Guard safe—</em>the armored Drakes" in chapter.markdown
	assert "loaded<em>.</em> Wait" in chapter.markdown
	assert "<em>what—</em>then stopped" in chapter.markdown
	assert "*run.*" in chapter.markdown
	assert "*I’d*" in chapter.markdown


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


def test_parse_chapter_keeps_leading_author_note():
	chapter = parse_chapter(
		_chapter_html(
			"The Depthless Doctor",
			"""
			<p><strong>Author's Note:</strong> This is setup for the story.</p>
			<p>Actual chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2018/07/09/the-depthless-doctor/",
	)

	assert "Author's Note" in chapter.markdown
	assert "Actual chapter text." in chapter.markdown


def test_parse_chapter_strips_trailing_author_note():
	chapter = parse_chapter(
		_chapter_html(
			"9.33",
			"""
			<p>Actual chapter text.</p>
			<p><strong>Author's Note:</strong> This should be stripped.</p>
			<p>More note text.</p>
			""",
		),
		"https://wanderinginn.com/2023/01/22/9-33/",
	)

	assert "Actual chapter text." in chapter.markdown
	assert "Author's Note" not in chapter.markdown
	assert "More note text." not in chapter.markdown


def test_parse_chapter_strips_trailing_plural_author_notes():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - Strategists at Sea (Pt. 2)",
			"""
			<p>Actual chapter text.</p>
			<p><strong>Author's Notes:</strong> This should be stripped.</p>
			<p>Gallery credits should be stripped too.</p>
			""",
		),
		"https://wanderinginn.com/2020/04/22/interlude-strategists-at-sea-pt-2/",
	)

	assert "Actual chapter text." in chapter.markdown
	assert "Author's Notes" not in chapter.markdown
	assert "Gallery credits" not in chapter.markdown


def test_parse_chapter_strips_after_chapter_thoughts_tail():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - A Meeting of [Druids]",
			"""
			<p>Actual chapter text.</p>
			<p><strong>After Chapter Thoughts:</strong> These should be stripped.</p>
			<p>Thanks to these wonderful artists.</p>
			<p><a href="https://ko-fi.com/example">https://ko-fi.com/example</a></p>
			<div class="tiled-gallery">
				<img src="https://example.com/fanart.png" alt="Fanart" />
			</div>
			""",
		),
		"https://wanderinginn.com/2020/07/01/interlude-a-meeting-of-druids/",
	)

	assert "Actual chapter text." in chapter.markdown
	assert "After Chapter Thoughts" not in chapter.markdown
	assert "wonderful artists" not in chapter.markdown
	assert "ko-fi.com" not in chapter.markdown
	assert "Fanart" not in chapter.markdown


def test_single_chapter_parse_keeps_after_chapter_thoughts_tail():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - A Meeting of [Druids]",
			"""
			<p>Actual chapter text.</p>
			<p><strong>After Chapter Thoughts:</strong> These should remain.</p>
			<p>Thanks to these wonderful artists.</p>
			""",
		),
		"https://wanderinginn.com/2020/07/01/interlude-a-meeting-of-druids/",
		options=SINGLE_CHAPTER_PARSE_OPTIONS,
	)

	assert "Actual chapter text." in chapter.markdown
	assert "After Chapter Thoughts" in chapter.markdown
	assert "wonderful artists" in chapter.markdown


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


def test_parse_chapter_removes_volume_seven_rfantasy_notice():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - Strategists at Sea (Pt. 2)",
			"""
			<p><strong>(I will be taking part in an online panel on r/Fantasy on the 23rd
			of April! <a href="https://example.com">Find out more here!</a>)</strong></p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/04/22/interlude-strategists-at-sea-pt-2/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "r/Fantasy" not in chapter.markdown


def test_parse_chapter_removes_volume_seven_rfantasy_notice_with_superscript_ordinal():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - Strategists at Sea (Pt. 1)",
			"""
			<p><strong>(I will be taking part in an online panel on r/Fantasy on the
			23<sup>rd</sup> of April! <a href="https://example.com">Find out more here!</a>)</strong></p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/04/19/interlude-strategists-at-sea-pt-1/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "r/Fantasy" not in chapter.markdown


def test_parse_chapter_removes_volume_seven_mouthymaven_notice():
	chapter = parse_chapter(
		_chapter_html(
			"7.17 S",
			"""
			<p><strong>(MouthyMaven (Andrea Parsneau) is recording The Wandering Inn’s
			Volume 2 audiobook on her server! You can check her out, but be warned–it’s
			live recording, mistakes, swearing, and all!
			<a href="https://example.com">You can find her server here, as well as times
			when she records!</a>)</strong></p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/04/12/7-17-s/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "MouthyMaven" not in chapter.markdown


def test_parse_chapter_removes_leading_promotional_notice():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - A Meeting of [Druids]",
			"""
			<p><strong>(A preview of Volume 2 is now up on Soundcloud!
			<a href="https://example.com">Check it out here!</a>
			The audiobook will be release July 14th!)</strong></p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/07/01/interlude-a-meeting-of-druids/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "Soundcloud" not in chapter.markdown
	assert "audiobook will be release" not in chapter.markdown


def test_parse_chapter_removes_multiple_leading_notice_paragraphs():
	chapter = parse_chapter(
		_chapter_html(
			"7.37",
			"""
			<p>(The Last Tide is available for preorder! It comes out in August!
			Check it out <a href="https://example.com">here</a>!)</p>
			<p>(One of our subreddit mods, Akrasia, is putting on a poll for TWI-readers,
			like last year! Consider filling it out!)</p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/07/29/7-37/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "Last Tide" not in chapter.markdown
	assert "Akrasia" not in chapter.markdown
	assert "subreddit mods" not in chapter.markdown


def test_parse_chapter_removes_leading_app_store_links():
	chapter = parse_chapter(
		_chapter_html(
			"7.46 K",
			"""
			<p>(The Living Library is an app with a number of interactive stories!
			A friend of mine, Quill, has finished The Sorcerer's Tower—give it a read
			if you're looking for more stories!)</p>
			<p>Android: https://play.google.com/store/apps/details?id=com.humbletoymaker</p>
			<p>iOS: https://apps.apple.com/us/app/the-living-library/id1522167504</p>
			<p>Real chapter text.</p>
			""",
		),
		"https://wanderinginn.com/2020/09/13/7-46-k/",
	)

	assert "Real chapter text." in chapter.markdown
	assert "Living Library" not in chapter.markdown
	assert "play.google.com" not in chapter.markdown
	assert "apps.apple.com" not in chapter.markdown


def test_parse_chapter_preserves_story_parenthetical_opening():
	chapter = parse_chapter(
		_chapter_html(
			"Interlude - The Antinium Wars (Pt.1)",
			"""
			<p>(This book was found by Ryoka Griffon on sale in Celum shortly after she
			arrived in this world.)</p>
			<p>More story text.</p>
			""",
		),
		"https://wanderinginn.com/2017/06/25/s02-the-antinium-wars-pt-1/",
	)

	assert "This book was found by Ryoka Griffon" in chapter.markdown
	assert "More story text." in chapter.markdown


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
