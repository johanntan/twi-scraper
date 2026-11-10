"""Render chapters as Markdown.

Escaping is deliberately minimal: the files are meant to be read as plain
text by a screen reader, so stray backslashes would be read aloud.
"""

from __future__ import annotations

import re
from typing import Callable

from .model import Break, Chapter, Em, Heading, Link, Para, Redaction, Rule, Strong, Text, norm_url

Resolver = Callable[[str], "str | None"]

_LINE_START = re.compile(r"^(\s*)([#>+\-]|\d+[.)])(\s)")


def _esc(text: str) -> str:
    text = text.replace("*", r"\*").replace("`", r"\`")
    # "<word" would be swallowed as an HTML tag by Markdown renderers.
    return re.sub(r"<(?=[A-Za-z/!?])", r"\\<", text)


def _wrap(marker: str, inner: str) -> str:
    stripped = inner.strip()
    if not stripped:
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    return f"{lead}{marker}{stripped}{marker}{trail}"


class Notes:
    """Footnotes holding redacted text; labels are unique within one file."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self.items: list[tuple[str, str]] = []

    def add(self, text: str) -> str:
        label = f"{self.prefix}{len(self.items) + 1}"
        self.items.append((label, text))
        return label

    def render(self) -> str:
        return "\n".join(f"[^{label}]: Redacted text: {_esc(text)}" for label, text in self.items)


def render_inlines(nodes: list, resolve: Resolver, notes: Notes | None = None) -> str:
    out: list[str] = []
    for n in nodes:
        if isinstance(n, Text):
            out.append(_esc(n.text))
        elif isinstance(n, Break):
            out.append("  \n")
        elif isinstance(n, Redaction):
            out.append(_esc(n.display()))
            if n.reveal and notes is not None:
                # A space keeps "[redacted] [^1]" from parsing as a reference link.
                out.append(f" [^{notes.add(n.reveal)}]")
        elif isinstance(n, Em):
            out.append(_wrap("*", render_inlines(n.children, resolve, notes)))
        elif isinstance(n, Strong):
            out.append(_wrap("**", render_inlines(n.children, resolve, notes)))
        elif isinstance(n, Link):
            inner = render_inlines(n.children, resolve, notes)
            target = resolve(n.href)
            if target is None:
                out.append(inner)
            else:
                if re.search(r"[\s()<>]", target):
                    target = f"<{target}>"
                out.append(f"[{inner.strip()}]({target})")
    return "".join(out)


def render_blocks(blocks: list, resolve: Resolver, heading_level: int = 2, notes: Notes | None = None) -> str:
    parts: list[str] = []
    for b in blocks:
        if isinstance(b, Rule):
            parts.append("***")
        elif isinstance(b, Heading):
            level = min(6, heading_level + b.level - 1)
            parts.append(f"{'#' * level} {b.text}")
        elif isinstance(b, Para):
            text = render_inlines(b.inlines, resolve, notes).strip()
            if text:
                parts.append(_LINE_START.sub(r"\1\\\2\3", text, count=1))
    return "\n\n".join(parts)


def slugify(title: str) -> str:
    """GitHub-style heading anchor."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def external_only(href: str) -> str | None:
    """Default resolver: drop links to the site, keep other links."""
    return None if norm_url(href) else href


def chapter_markdown(ch: Chapter, resolve: Resolver = external_only, level: int = 1, note_prefix: str = "") -> str:
    notes = Notes(note_prefix)
    body = render_blocks(ch.blocks, resolve, heading_level=level + 1, notes=notes)
    foot = f"\n\n{notes.render()}" if notes.items else ""
    return f"{'#' * level} {ch.title}\n\n{body}{foot}\n"


def single_file(title: str, chapters: list[Chapter]) -> str:
    """One Markdown document; links between included chapters become anchors."""
    anchors: dict[str, str] = {}
    used: dict[str, int] = {}
    for ch in chapters:
        slug = slugify(ch.title) or "chapter"
        n = used.get(slug, 0)
        used[slug] = n + 1
        anchor = slug if n == 0 else f"{slug}-{n}"
        for u in ch.urls():
            anchors.setdefault(norm_url(u) or u, anchor)

    def resolve(href: str) -> str | None:
        n = norm_url(href)
        if n is None:
            return href
        a = anchors.get(n)
        return f"#{a}" if a else None

    parts = [f"# {title}\n"] + [
        chapter_markdown(ch, resolve, level=2, note_prefix=f"c{i}-") for i, ch in enumerate(chapters, 1)
    ]
    return "\n".join(parts)


def folder_resolver(files: dict[str, str]) -> Resolver:
    """Resolver for a folder of chapter files: url -> relative file name."""
    def resolve(href: str) -> str | None:
        n = norm_url(href)
        if n is None:
            return href
        return files.get(n)
    return resolve
