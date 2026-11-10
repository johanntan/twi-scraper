import zipfile
import xml.dom.minidom

from twi.cli import flatten_by_chapter_marks, main
from twi.epub import write_epub
from twi.markdown import chapter_markdown, single_file
from twi.model import Break, Chapter, Em, Heading, Link, Para, Rule, Strong, Text, norm_url

S4 = "https://wanderinginn.com/2020/12/23/solstice-pt-4/"


def para(*nodes):
    return Para(list(nodes))


def test_markdown_formatting_and_minimal_escaping():
    ch = Chapter("1.00", None, [
        para(Text("She said "), Em([Text("no ")]), Text("and "), Strong([Text("meant")]), Text(" it.")),
        Rule(),
        para(Text("[Skill – Basic Cooking obtained!] 5 * 3 <Query>")),
        para(Text("- not a list"), Break(), Text("line two")),
    ])
    md = chapter_markdown(ch)
    assert md.startswith("# 1.00\n\n")
    assert "She said *no* and **meant** it." in md
    assert "\n\n***\n\n" in md
    assert r"[Skill – Basic Cooking obtained!] 5 \* 3 \<Query>" in md  # brackets left alone
    assert "\\- not a list  \nline two" in md


def test_single_chapter_drops_site_links_keeps_text():
    ch = Chapter("Solstice (Pt. 3)", None, [para(Link(S4, [Em([Text("Changed.")])]))])
    assert chapter_markdown(ch).strip().endswith("*Changed.*")


def test_single_file_links_become_anchors():
    a = Chapter("Solstice (Pt. 3)", "https://wanderinginn.com/2020/12/23/solstice-pt-3/",
                [para(Link(S4, [Text("Changed.")]))])
    b = Chapter("Solstice (Pt. 4)", S4, [para(Text("Fading."))])
    md = single_file("Volume 7", [a, b])
    assert "[Changed.](#solstice-pt-4)" in md
    assert "## Solstice (Pt. 4)" in md


def test_epub_is_valid_and_links_are_internal(tmp_path):
    a = Chapter("Solstice (Pt. 3)", "https://wanderinginn.com/2020/12/23/solstice-pt-3/", [
        para(Text("Fish & chips < 3")), Rule(), Heading(1, "Part"),
        para(Link(S4, [Text("Changed.")])),
        para(Link("https://wanderinginn.com/2020/12/13/7-62/", [Text("not in book")])),
    ])
    b = Chapter("Solstice (Pt. 4)", S4, [para(Text("Fading."))])
    path = tmp_path / "v.epub"
    write_epub(path, "Volume 7", [a, b])
    with zipfile.ZipFile(path) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        for name in z.namelist():
            if name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                xml.dom.minidom.parseString(z.read(name))  # raises if malformed
        c1 = z.read("OEBPS/chap0001.xhtml").decode()
        assert '<a href="chap0002.xhtml">Changed.</a>' in c1
        assert "not in book" in c1 and "7-62" not in c1
        assert "Fish &amp; chips &lt; 3" in c1 and "<hr/>" in c1
        nav = z.read("OEBPS/nav.xhtml").decode()
        assert nav.index("Pt. 3") < nav.index("Pt. 4")


def test_flatten_by_chapter_marks_regroups_parts():
    p1 = Chapter("Griefman (Pt. 1)", "https://wanderinginn.com/2024/09/14/griefman-pt-1/", [
        para(Strong([Text("Foreword:")])), para(Text("Intro.")),
        Heading(1, "Chapter 1"), para(Text("a")), Heading(1, "Chapter 2"), para(Text("b")),
    ])
    p2 = Chapter("Griefman (Pt. 2)", "https://wanderinginn.com/2024/09/14/griefman-pt-2/", [
        para(Text("b continued")), Heading(1, "Chapter 3"), para(Text("c")),
    ])
    out = flatten_by_chapter_marks("Griefman", [p1, p2])
    assert [c.title for c in out] == ["Foreword", "Chapter 1", "Chapter 2", "Chapter 3"]
    assert p2.url in out[2].aliases  # part 2 starts mid-chapter 2
    assert len(out[2].blocks) == 2


def test_norm_url():
    assert norm_url("http://www.WanderingInn.com/2017/03/03/rw1-00?x=1#c") == "https://wanderinginn.com/2017/03/03/rw1-00/"
    assert norm_url("https://ko-fi.com/brack") is None


def test_rejects_non_site_url(capsys):
    assert main(["chapter", "https://example.com/story/"]) == 1
    assert "not a wanderinginn.com URL" in capsys.readouterr().err
