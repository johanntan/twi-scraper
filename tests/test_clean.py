from twi.clean import CONTENT_WARNING_TEXT, clean
from twi.model import Em, Heading, Link, Para, Rule, Strong, plain_text


def article(body: str) -> str:
    return f'<article class="twi-article">{body}</article>'


NAV = (
    '<hr /><p><a href="https://wanderinginn.com/2026/10/18/10-77-mm/">Previous Chapter</a> '
    '<a href="https://wanderinginn.com/2026/11/07/10-79-rvp/"><span style="float: right;">Next Chapter</span></a></p>'
)


def texts(blocks):
    out = []
    for b in blocks:
        if isinstance(b, Rule):
            out.append("---")
        elif isinstance(b, Heading):
            out.append(f"# {b.text}")
        else:
            out.append(plain_text(b.inlines))
    return out


def test_dash_separators_become_single_rules():
    html = article(
        "<p>One.</p><p>&nbsp;</p><p>——</p><p>&nbsp;</p><p>Two.</p>"
        "<p>&#8212;-</p><p>—–</p><p>Three.</p><p>* * *</p>" + NAV
    )
    assert texts(clean(html).blocks) == ["One.", "---", "Two.", "---", "Three."]


def test_single_dash_paragraph_is_story_text():
    assert texts(clean(article("<p>A</p><p>—</p><p>B</p>")).blocks) == ["A", "—", "B"]


def test_nav_links_removed():
    blocks = clean(article("<p>Story.</p>" + NAV)).blocks
    assert texts(blocks) == ["Story."]


def test_author_note_and_art_credits_stripped():
    html = article(
        "<p>Story starts.</p>" + "<p>More story.</p>" * 6 +
        "<p><strong>Author’s Note:</strong></p><p>I was tired.</p>"
        '<p><img src="x.jpg"></p><p>Erin by Brack!</p>'
        '<p>Ko-Fi: <a href="https://ko-fi.com/brack">https://ko-fi.com/brack</a></p>' + NAV
    )
    res = clean(html)
    assert texts(res.blocks)[-1] == "More story."
    assert "I was tired." not in texts(res.blocks)


def test_keep_notes_puts_note_under_heading_and_drops_credits():
    html = article(
        "<p>Story.</p>" * 6 +
        "<p><strong>Author’s Note:</strong> I was tired.</p><p>See you next time!</p>"
        "<p>Erin by Brack!</p>"
        '<p>Twitter: <a href="https://twitter.com/x">https://twitter.com/x</a></p>' + NAV
    )
    out = texts(clean(html, keep_notes=True).blocks)
    assert out[-4:] == ["---", "# Author’s Note", "I was tired.", "See you next time!"]


def test_after_chapter_thoughts_is_an_author_note():
    html = article("<p>Story.</p>" * 6 + "<p><strong>After Chapter Thoughts:</strong> Back!</p><p>Bye.</p>")
    assert texts(clean(html).blocks) == ["Story."] * 6


def test_9_68_style_announcements_removed_with_content_warning_and_alternate():
    html = article(
        '<p><strong>(This chapter has a trigger warning for disturbing content. '
        '<a href="https://wanderinginn.com/warnings/">Click here for details.</a>)</strong></p>'
        '<p><strong>[A trigger-free version of the chapter '
        '<a href="https://wanderinginn.com/9-68-trigger-free/">is located here.</a> '
        "The password is ‘traumaFree’ without apostrophes.]</strong></p>"
        "<p><strong>&lt;A summary has also been written here.&gt;</strong></p>"
        "<p><strong>{I released this chapter early.}</strong></p>"
        "<p>&nbsp;</p><p>They came out of the tunnels.</p>" + NAV
    )
    res = clean(html)
    assert texts(res.blocks) == [CONTENT_WARNING_TEXT, "They came out of the tunnels."]
    assert res.alternates["trigger-free"] == ("https://wanderinginn.com/9-68-trigger-free/", "traumaFree")


def test_alternates_found_when_notes_kept():
    html = article(
        '<p><strong>[Trigger-free version <a href="https://wanderinginn.com/9-68-trigger-free/">here</a>. '
        "The password is ‘traumaFree’.]</strong></p><p>Story.</p>"
    )
    res = clean(html, keep_notes=True)
    assert res.alternates["trigger-free"][1] == "traumaFree"
    assert len(res.blocks) == 2


def test_multi_paragraph_bracket_announcement_and_promo_links():
    html = article(
        "<p>[To celebrate the audiobook release on April 30th…</p><p>Undead and more.</p>"
        "<p>And don’t forget Cognita…]</p>"
        '<p>Android: <a href="https://play.google.com/x">https://play.google.com/x</a></p>'
        "<p>&nbsp;</p><p>Click.</p>"
    )
    assert texts(clean(html).blocks) == ["Click."]


def test_skill_and_query_openers_are_kept():
    html = article("<p>[Innkeeper Level 4!]</p><p>&lt;Query — Response?&gt;</p><p>Erin woke.</p>")
    assert texts(clean(html).blocks) == ["[Innkeeper Level 4!]", "<Query — Response?>", "Erin woke."]


def test_links_to_chapters_are_story_text_not_promos():
    html = article(
        "<p>And Ryoka—</p>"
        '<p><a href="https://wanderinginn.com/2020/12/23/solstice-pt-9/">—Saw.</a></p>' + NAV
    )
    blocks = clean(html).blocks
    assert texts(blocks) == ["And Ryoka—", "—Saw."]
    assert isinstance(blocks[-1].inlines[0], Link)


def test_trailing_bold_reading_order_note_removed():
    html = article(
        "<p>Everything…</p><p><em>Changed.</em></p>"
        "<p><strong>(Before going to next chapter, read Solstice Pt. 4-9.)</strong></p>" + NAV
    )
    assert texts(clean(html).blocks) == ["Everything…", "Changed."]


def test_galleries_and_images_removed_and_formatting_kept():
    html = article(
        '<p>She said <i>no</i> and <b>meant</b> it.<br/>Twice.</p>'
        '<div class="tiled-gallery"><div class="gallery-row"><img src="a.jpg"/></div></div>'
        '<p><span class="mrsha-write">Hello!</span> <span style="color:#99cc00">green</span></p>'
    )
    blocks = clean(html).blocks
    assert len(blocks) == 2
    first = blocks[0].inlines
    assert any(isinstance(n, Em) for n in first) and any(isinstance(n, Strong) for n in first)
    assert isinstance(blocks[1].inlines[0], Em)
    assert plain_text(blocks[1].inlines) == "Hello! green"


def test_chapter_marks_become_headings():
    html = article("<p><strong>Chapter 4</strong></p><p>Roy did not attend.</p>")
    blocks = clean(html, chapter_marks=True).blocks
    assert isinstance(blocks[0], Heading) and blocks[0].text == "Chapter 4"
    assert isinstance(clean(html).blocks[0], Para)
