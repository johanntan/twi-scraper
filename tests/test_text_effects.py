"""Redactions (7.25), look-alike "font" letters (Volume 10), password safety."""

import zipfile

import pytest

from twi.clean import clean
from twi.cli import Passwords
from twi.epub import write_epub
from twi.markdown import chapter_markdown
from twi.model import Chapter, Redaction, Text, plain_text
from twi.site import Page, Site, SiteBlocked
from twi.unistyle import normalize


def article(body):
    return f'<article class="twi-article">{body}</article>'


# --- redactions ---------------------------------------------------------------


def test_redaction_comment_becomes_reveal():
    res = clean(article("<p>There were ███<!--six--> of them.</p>"))
    nodes = res.blocks[0].inlines
    red = next(n for n in nodes if isinstance(n, Redaction))
    assert red.reveal == "six"
    assert plain_text(nodes) == "There were [redacted] of them."


def test_redaction_group_and_partial_word_are_rebuilt():
    res = clean(article(
        "<p>███, ███, █████, ████…<!--one, two, three, four-->she lost track.</p>"
        "<p>One of them had been flying with █i█g█.<!--wns--></p>"
    ))
    reds = [n for b in res.blocks for n in b.inlines if isinstance(n, Redaction)]
    assert [r.reveal for r in reds] == ["one, two, three, four", "wings"]
    assert "[partly redacted: ?i?g?]" in plain_text(res.blocks[1].inlines)


def test_chapter_opening_with_redaction_is_not_mistaken_for_an_announcement():
    res = clean(article("<p>███, ███<!--one, two-->. She lost track.</p><p>Then more.</p>"))
    assert len(res.blocks) == 2 and not res.log


def test_redaction_without_comment_has_no_reveal_and_other_comments_ignored():
    res = clean(article("<p>A ████ word.</p><p>Plain<!-- close group --> text.</p>"))
    red = next(n for n in res.blocks[0].inlines if isinstance(n, Redaction))
    assert red.reveal is None
    assert plain_text(res.blocks[1].inlines) == "Plain text."


def test_redaction_footnotes_in_markdown_and_epub(tmp_path):
    ch = Chapter("7.25", None, clean(article("<p>There were ███<!--six--> of them.</p>")).blocks)
    md = chapter_markdown(ch)
    assert "There were [redacted] [^1] of them." in md
    assert "[^1]: Redacted text: six" in md
    path = tmp_path / "c.epub"
    write_epub(path, "7.25", [ch])
    xhtml = zipfile.ZipFile(path).read("OEBPS/chap0001.xhtml").decode()
    assert 'epub:type="noteref"' in xhtml and 'href="#note1">[redacted]</a>' in xhtml
    assert '<aside epub:type="footnote" role="doc-footnote" id="note1">' in xhtml
    assert "Redacted text: six" in xhtml


# --- look-alike font letters --------------------------------------------------


@pytest.mark.parametrize("raw, plain", [
    ("Dᴇᴀᴛʜ ʜᴀs ᴄᴏᴍᴇ ғᴏʀ ʏᴏᴜ, Kᴀsɪɢɴᴀ.", "Death has come for you, Kasigna."),
    ("ᴡᴀꜱ ᴀ ɢᴏᴅ.", "Was a god."),
    ("ᴍᴏʀᴇ ᴏɴ ᴘᴀɢᴇ 𝟦!", "More on page 4!"),
    ("Effectᴺᵒ ᴿᶦᵍʰᵗˢ ᴿᵉˢᵉʳᵛᵉᵈ, which", "Effect No Rights Reserved, which"),
    ("Sɐʇɐɹ", "Satar"),
    (": ˥ǝʍpbnᴉll¿ ∀ɹǝ ʎon sʇᴉll ʇɥǝɹǝ¿ I’p lᴉʞǝ ɐ ɯoɯǝuʇ˙ ┴ɥᴉs ᴉs Sɐʇɐɹ Sᴉlʌǝɹɟɐuƃ’ ]Hᴉsʇoɹᴉɐu oɟ ʇɥǝ Moɹlp[˙",
     ": Lewdquill? Are you still there? I’d like a moment. This is Satar Silverfang, [Historian of the World]."),
])
def test_styled_letters_become_plain(raw, plain):
    assert "".join(t for t, _ in normalize(raw)) == plain


@pytest.mark.parametrize("text", ["Smile™.", "5 m²", "¿Qué?", "Chóvain", "café", "Erin’s inn"])
def test_ordinary_text_untouched(text):
    assert normalize(text) == [(text, None)]


def test_small_caps_keep_their_look_in_epub(tmp_path):
    blocks = clean(article("<p>“Dᴇᴀᴛʜ ʜᴀs ᴄᴏᴍᴇ.” Effectᴺᵒ</p>")).blocks
    assert any(isinstance(n, Text) and n.style == "sc" for n in blocks[0].inlines)
    path = tmp_path / "s.epub"
    write_epub(path, "x", [Chapter("x", None, blocks)])
    xhtml = zipfile.ZipFile(path).read("OEBPS/chap0001.xhtml").decode()
    assert '<span class="sc">“Death has come.”</span>' in xhtml
    assert "<sup> No</sup>" in xhtml


# --- password safety ----------------------------------------------------------


class FakeSite:
    """Locked pages behind one Patreon tier; counts every unlock attempt."""

    def __init__(self, password):
        self.password = password
        self.attempts = []

    def fetch(self, url):
        return Page(url, url, "", lock="patreon", tier="Blue Fruit Juice")

    def unlock(self, page, pw):
        self.attempts.append(pw)
        if pw == self.password:
            return Page(page.url, page.url, "<p>ok</p>")
        return None


def test_saved_password_that_works_is_reused_and_wrong_one_not_retried():
    site = FakeSite("right")
    pw = Passwords(["wrong", "right"], skip_locked=True)
    for i in range(5):
        assert pw.fetch(site, f"https://wanderinginn.com/c{i}/", f"c{i}") is not None
    # 'wrong' sent once ever, then only the known-good password.
    assert site.attempts == ["wrong", "right", "right", "right", "right", "right"]


def test_wrong_saved_password_sent_once_per_tier():
    site = FakeSite("right")
    pw = Passwords(["stale"], skip_locked=True)
    for i in range(10):
        assert pw.fetch(site, f"https://wanderinginn.com/c{i}/", f"c{i}") is None
    assert site.attempts == ["stale"]
    assert len(pw.skipped) == 10


def test_firewall_page_raises_blocked(monkeypatch):
    class R:
        status_code = 403
        text = "<p>WP Remote Firewall</p><p>Blocked because of Malicious Activities</p>"
    site = Site(delay=0)
    monkeypatch.setattr(site.session, "request", lambda *a, **k: R())
    with pytest.raises(SiteBlocked):
        site._request("GET", "https://wanderinginn.com/x/")
