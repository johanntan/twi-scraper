"""Document model shared by the cleaner and the Markdown/EPUB writers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# --- inline nodes -----------------------------------------------------------


@dataclass
class Text:
    text: str
    # Visual style the text had as look-alike Unicode ("sc" small caps, "sup"
    # superscript). The text itself is plain letters; only EPUB shows the style.
    style: str | None = None


@dataclass
class Em:
    children: list


@dataclass
class Strong:
    children: list


@dataclass
class Link:
    href: str
    children: list


@dataclass
class Break:
    pass


@dataclass
class Redaction:
    """Blacked-out text (█). `reveal` is the hidden original, when the page has it.

    7.25 hides the words in an HTML comment right after the blocks:
    ``███<!--six-->``. Writers show `display()` inline and put `reveal` in a footnote.
    """

    text: str
    reveal: str | None = None

    def display(self) -> str:
        return redaction_display(self.text)


BLOCK_CHAR = "█"
REDACTED_WORD = re.compile(r"[\w'’\-]*█[█\w'’\-]*")


def redaction_display(text: str) -> str:
    """Screen-reader wording: "███" -> "[redacted]", "█i█g█" -> "[partly redacted: ?i?g?]"."""
    def word(m: re.Match) -> str:
        w = m.group(0)
        if not w.strip(BLOCK_CHAR):
            return "[redacted]"
        return f"[partly redacted: {w.replace(BLOCK_CHAR, '?')}]"
    return REDACTED_WORD.sub(word, text)


# --- block nodes ------------------------------------------------------------


@dataclass
class Para:
    inlines: list


@dataclass
class Rule:
    pass


@dataclass
class Heading:
    """A heading inside a chapter. Level 1 = directly below the chapter title."""

    level: int
    text: str


# --- chapters ---------------------------------------------------------------


@dataclass
class Chapter:
    title: str
    url: str | None
    blocks: list
    # Other site URLs whose content lives in this chapter (e.g. Griefman parts).
    aliases: list[str] = field(default_factory=list)

    def urls(self) -> list[str]:
        out = [self.url] if self.url else []
        return out + list(self.aliases)


# --- helpers ----------------------------------------------------------------


def plain_text(inlines: list, raw_redactions: bool = False) -> str:
    """Text of an inline tree. raw_redactions: keep "███" instead of "[redacted]"
    (the cleaner's heuristics must not mistake "[redacted]" for a bracketed note)."""
    parts: list[str] = []
    for node in inlines:
        if isinstance(node, Text):
            parts.append(node.text)
        elif isinstance(node, Break):
            parts.append("\n")
        elif isinstance(node, Redaction):
            parts.append(node.text if raw_redactions else node.display())
        else:
            parts.append(plain_text(node.children, raw_redactions))
    return "".join(parts)


SITE_HOST = "wanderinginn.com"


def norm_url(url: str) -> str | None:
    """Canonical form of a wanderinginn.com URL, or None for other sites."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    host = parts.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host != SITE_HOST:
        return None
    path = parts.path or "/"
    if not path.endswith("/"):
        path += "/"
    return f"https://{SITE_HOST}{path.lower()}"
