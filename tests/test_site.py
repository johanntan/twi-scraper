from twi.site import ChapterRef, _norm_title, parse_archive, parse_page, parse_toc

URL = "https://wanderinginn.com/2026/11/07/10-79-rvp/"


def page(content: str, extra_head: str = "") -> str:
    return (
        f"<html><head><title>10.79 RVP - The Wandering Inn</title>{extra_head}</head><body>"
        '<div data-widget_type="theme-post-content.default"><div class="elementor-widget-container">'
        f"{content}</div></div><h3>Chapter Gallery</h3><img src='g.jpg'></body></html>"
    )


def test_parse_open_chapter():
    p = parse_page(URL, page(
        '<main><article class="twi-article"><p>Hi.</p>'
        '<p><a href="https://wanderinginn.com/2026/11/14/10-80/">Next Chapter</a></p></article></main>'
    ))
    assert p.lock is None and p.title == "10.79 RVP"
    assert "Hi." in p.content_html and "Chapter Gallery" not in p.content_html
    assert p.next_url == "https://wanderinginn.com/2026/11/14/10-80/"


def test_parse_patreon_lock_and_bad_password_flag():
    html = page('<div class="patreon-protected-post"><h2>Patreon Exclusive</h2></div>',
                '<script>const HYBRID_BAD_PASSWORD = "1";</script>')
    p = parse_page(URL, html)
    assert p.lock == "patreon" and p.bad_password


def test_parse_wordpress_password_form():
    p = parse_page(URL, page('<form action="/wp-login.php?action=postpass"><input name="post_password"/></form>'))
    assert p.lock == "wp"


def test_parse_page_without_article_wrapper():
    p = parse_page(URL, page("<p>(This is the edited version.)</p><p>They came out.</p>"))
    assert p.lock is None and "They came out." in p.content_html


def test_parse_toc():
    html = """
    <div id="vol-1" class="volume-wrapper"><h2 class="volume-title">Volume 1</h2>
      <div class="chapter-entry"><div class="body-web"><a href="https://wanderinginn.com/2017/03/03/rw1-00/">1.00</a></div></div>
    </div>
    <div id="vol-10" class="volume-wrapper"><h2 class="volume-title">Volume 10</h2>
      <div class="chapter-entry"><div class="body-web"><a href="https://wanderinginn.com/2026/09/26/tales-of-innworld-9/">Tales of Innworld #9</a></div></div>
      <div class="chapter-entry"><div class="body-web"><a href="https://wanderinginn.com/2026/10/03/interlude-cormeng-pt-1/">Interlude &#8212; Cormeng (Pt. 1)</a></div></div>
    </div>"""
    vols = parse_toc(html)
    assert [v.key for v in vols] == ["1", "10"]
    assert vols[1].chapters[0].is_extra and not vols[1].chapters[1].is_extra
    assert vols[1].chapters[1].title == "Interlude — Cormeng (Pt. 1)"


def test_parse_archive_skips_rewrite_links():
    html = page(
        '<p>See <a href="https://wanderinginn.com/2023/03/03/rw1-00/">here</a>.</p>'
        '<p><a href="https://wanderinginn.com/2016/07/27/1-00/">1.00</a><br/>'
        '<a href="https://wanderinginn.com/2016/09/04/interlude/">Interlude</a></p>'
    )
    vol = parse_archive(html)
    assert [c.title for c in vol.chapters] == ["1.00", "Interlude"]


def test_title_matching_normalisation():
    assert _norm_title("solstice pt 3") == _norm_title("Solstice (Pt. 3)")
    assert _norm_title("Interlude - Cormeng (Pt.1)") == _norm_title("Interlude — Cormeng (Pt. 1)")
    assert ChapterRef("Announcement — A Month’s Break", "u").is_extra
