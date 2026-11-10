"""Write chapters as an EPUB 3 file (with an EPUB 2 NCX for older readers)."""

from __future__ import annotations

import re
import uuid
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .model import Break, Chapter, Em, Heading, Link, Para, Redaction, Rule, Strong, Text, norm_url

_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

CSS = """\
body { font-family: serif; line-height: 1.5; margin: 0 5%; }
h1 { text-align: center; margin: 2em 0 1.5em; }
h2 { margin: 1.5em 0 1em; }
p { margin: 0 0 0.8em; text-indent: 0; }
hr { border: none; border-top: 1px solid currentColor; width: 30%; margin: 1.5em auto; }
.sc { font-variant: small-caps; }
aside { font-size: 0.9em; }
"""


def _x(text: str) -> str:
    return escape(_BAD_XML.sub("", text), quote=True)


def _inlines(nodes: list, resolve, notes: list[str]) -> str:
    out: list[str] = []
    for n in nodes:
        if isinstance(n, Text):
            if n.style == "sc":
                out.append(f'<span class="sc">{_x(n.text)}</span>')
            elif n.style == "sup":
                out.append(f"<sup>{_x(n.text)}</sup>")
            else:
                out.append(_x(n.text))
        elif isinstance(n, Break):
            out.append("<br/>")
        elif isinstance(n, Redaction):
            if n.reveal:
                notes.append(n.reveal)
                k = len(notes)
                # Pop-up footnote: the hidden words stay out of the reading flow.
                out.append(f'<a epub:type="noteref" role="doc-noteref" id="nref{k}" '
                           f'href="#note{k}">{_x(n.display())}</a>')
            else:
                out.append(_x(n.display()))
        elif isinstance(n, Em):
            out.append(f"<em>{_inlines(n.children, resolve, notes)}</em>")
        elif isinstance(n, Strong):
            out.append(f"<strong>{_inlines(n.children, resolve, notes)}</strong>")
        elif isinstance(n, Link):
            inner = _inlines(n.children, resolve, notes)
            target = resolve(n.href)
            out.append(inner if target is None else f'<a href="{_x(target)}">{inner}</a>')
    return "".join(out)


def _body(blocks: list, resolve) -> str:
    parts: list[str] = []
    notes: list[str] = []
    for b in blocks:
        if isinstance(b, Rule):
            parts.append("<hr/>")
        elif isinstance(b, Heading):
            lvl = min(6, b.level + 1)
            parts.append(f"<h{lvl}>{_x(b.text)}</h{lvl}>")
        elif isinstance(b, Para):
            inner = _inlines(b.inlines, resolve, notes).strip()
            if inner:
                parts.append(f"<p>{inner}</p>")
    for k, text in enumerate(notes, 1):
        parts.append(
            f'<aside epub:type="footnote" role="doc-footnote" id="note{k}">'
            f'<p>Redacted text: {_x(text)} <a href="#nref{k}" role="doc-backlink">Back</a></p></aside>'
        )
    return "\n".join(parts)


def _xhtml(title: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
        'lang="en" xml:lang="en">\n'
        f'<head><meta charset="utf-8"/><title>{_x(title)}</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def write_epub(path: Path, title: str, chapters: list[Chapter], author: str = "pirateaba") -> None:
    files = {}
    for i, ch in enumerate(chapters, 1):
        name = f"chap{i:04d}.xhtml"
        for u in ch.urls():
            files.setdefault(norm_url(u) or u, name)

    def resolve(href: str) -> str | None:
        n = norm_url(href)
        if n is None:
            return href
        return files.get(n)  # in this book -> internal link; otherwise plain text

    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'twi:' + title)}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    docs: list[tuple[str, str, str]] = []  # (file, title, xhtml)
    for i, ch in enumerate(chapters, 1):
        body = (
            f'<section epub:type="chapter" aria-labelledby="h{i}">\n'
            f'<h1 id="h{i}">{_x(ch.title)}</h1>\n{_body(ch.blocks, resolve)}\n</section>'
        )
        docs.append((f"chap{i:04d}.xhtml", ch.title, _xhtml(ch.title, body)))

    nav_items = "\n".join(f'<li><a href="{f}">{_x(t)}</a></li>' for f, t, _ in docs)
    nav = _xhtml(
        title,
        f'<nav epub:type="toc" id="toc" role="doc-toc">\n<h1>{_x(title)}</h1>\n<ol>\n{nav_items}\n</ol>\n</nav>\n'
        f'<nav epub:type="landmarks" hidden="">\n<ol>\n'
        f'<li><a epub:type="toc" href="nav.xhtml">Contents</a></li>\n'
        + (f'<li><a epub:type="bodymatter" href="{docs[0][0]}">Start</a></li>\n' if docs else "")
        + "</ol>\n</nav>",
    )
    nav_points = "\n".join(
        f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{_x(t)}</text></navLabel>'
        f'<content src="{f}"/></navPoint>'
        for i, (f, t, _) in enumerate(docs, 1)
    )
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        f'<head><meta name="dtb:uid" content="{book_id}"/></head>\n'
        f"<docTitle><text>{_x(title)}</text></docTitle>\n<navMap>\n{nav_points}\n</navMap>\n</ncx>\n"
    )
    manifest = "\n".join(
        f'<item id="c{i}" href="{f}" media-type="application/xhtml+xml"/>'
        for i, (f, _, _) in enumerate(docs, 1)
    )
    spine = "\n".join(f'<itemref idref="c{i}"/>' for i in range(1, len(docs) + 1))
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
        f"<dc:title>{_x(title)}</dc:title>\n<dc:creator>{_x(author)}</dc:creator>\n"
        f'<dc:language>en</dc:language>\n<meta property="dcterms:modified">{modified}</meta>\n'
        '<meta property="schema:accessMode">textual</meta>\n'
        '<meta property="schema:accessModeSufficient">textual</meta>\n'
        '<meta property="schema:accessibilityFeature">structuralNavigation</meta>\n'
        '<meta property="schema:accessibilityFeature">tableOfContents</meta>\n'
        '<meta property="schema:accessibilityHazard">none</meta>\n'
        "</metadata>\n<manifest>\n"
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
        '<item id="css" href="style.css" media-type="text/css"/>\n'
        f"{manifest}\n</manifest>\n"
        f'<spine toc="ncx">\n<itemref idref="nav" linear="no"/>\n{spine}\n</spine>\n</package>\n'
    )
    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles>\n</container>\n"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        deflate = dict(compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/container.xml", container, **deflate)
        z.writestr("OEBPS/content.opf", opf, **deflate)
        z.writestr("OEBPS/nav.xhtml", nav, **deflate)
        z.writestr("OEBPS/toc.ncx", ncx, **deflate)
        z.writestr("OEBPS/style.css", CSS, **deflate)
        for f, _, doc in docs:
            z.writestr(f"OEBPS/{f}", doc, **deflate)
    tmp.replace(path)
