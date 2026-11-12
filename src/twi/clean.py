"""Turn a chapter's HTML into clean blocks.

Removes navigation links, author's notes, fan art, galleries and leading
announcements; turns the author's dash separators into proper rules.
See CLAUDE.md for the site markup these rules are based on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .model import Break, Em, Heading, Link, Para, Redaction, Rule, Strong, Text, norm_url, plain_text
from .unistyle import normalize as normalize_styled

# Tags whose content never belongs in the text.
DROP_TAGS = {
    "script", "style", "noscript", "iframe", "img", "picture", "svg", "figure",
    "meta", "link", "form", "input", "button", "video", "audio", "source",
    "canvas", "object", "embed", "aside", "template", "select", "textarea",
}
# Classes of elements to drop wholesale (galleries, embeds).
DROP_CLASSES = re.compile(
    r"tiled-gallery|wp-block-gallery|\bgallery\b|twitter-tweet|wp-block-embed|"
    r"sharedaddy|jp-relatedposts|wpcnt|patreon-protected-post"
)
BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "header", "footer", "blockquote",
    "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody", "tr", "td",
    "th", "center", "pre", "address", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
    "details", "summary", "nav",
}
LEAF_BLOCKS = {"p", "li", "dt", "dd", "pre", "address", "h1", "h2", "h3", "h4", "h5", "h6", "summary"}
EM_TAGS = {"em", "i", "cite", "var", "dfn"}
STRONG_TAGS = {"strong", "b"}
EM_CLASSES = {"mrsha-write"}

WS = re.compile(r"[\s ​﻿]+")
SEPARATOR = re.compile(r"^[\-‐-―−_*~=+#•·◦⁂∗\s]+$")
NAV_WORDS = re.compile(r"(previous|next)\s+chapter|table\s+of\s+contents|\bindex\b", re.I)
# "Author's Note:" and the older "After Chapter Thoughts:" label (Volume 7 era).
NOTE_LABEL = r"\W{0,3}(?:author[’'`]?s?\s*['’]?\s*notes?|after[\s-]*chapter\s+thoughts)"
AUTHOR_NOTE = re.compile(rf"^{NOTE_LABEL}", re.I)
CHAPTER_MARK = re.compile(r"^chapter\s+(\d+|[ivxlc]+)$", re.I)
URLISH = re.compile(r"^(https?://|www\.)\S+$", re.I)
CW_WORDS = re.compile(r"trigger[\s-]*warning|content\s+warning", re.I)
PASSWORD_HINT = re.compile(r"password\s+is\s+(?:also\s+)?[‘'\"“]?([^\s‘’'\"“”]+?)[’'\"”]?(?=[\s.,;)\]}>]|$)", re.I)
PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}
ANNOUNCE_WORDS = re.compile(
    r"\b(patreon|patrons?|author|audiobook|ebook|pre-?order|release[sd]?|update|"
    r"on break|public readers|chapter|warning|password|discord|webcomic)\b", re.I)

CONTENT_WARNING_TEXT = "Content warning: this chapter has a trigger warning for disturbing content."


@dataclass
class CleanResult:
    blocks: list
    log: list[str] = field(default_factory=list)
    content_warning: bool = False
    # kind ("trigger-free" / "summary") -> (url, password or None)
    alternates: dict[str, tuple[str, str | None]] = field(default_factory=dict)


# --- HTML -> raw blocks -----------------------------------------------------


def _classes(tag: Tag) -> str:
    return " ".join(tag.get("class") or [])


_SEP = r"[\s,.!?…;:]"
_RWORD = r"[\w'’\-]*█[█\w'’\-]*"
REDACTED_GROUP_AT_END = re.compile(rf"({_RWORD}(?:{_SEP}{{1,3}}{_RWORD})*)({_SEP}{{0,3}})$")
REDACTED_RUN = re.compile(rf"{_RWORD}(?:{_SEP}{{1,3}}{_RWORD})*")


def _fill_redaction(group: str, hidden: str) -> str:
    """Rebuild the original words: 7.25 hides exactly one letter per █.

    "███, ███" + "one, two" -> "one, two"; "█i█g█" + "wns" -> "wings".
    Falls back to the comment text if the counts don't line up.
    """
    letters = [c for c in hidden if c.isalnum()]
    if group.count("█") != len(letters):
        return hidden
    it = iter(letters)
    return "".join(next(it) if c == "█" else c for c in group)


def _mark_redactions(root: Tag) -> None:
    """Pair "███<!--hidden words-->" so the comment isn't lost when comments go."""
    for comment in list(root.find_all(string=lambda s: isinstance(s, Comment))):
        prev = comment.previous_sibling
        if not isinstance(prev, NavigableString) or isinstance(prev, Comment):
            continue
        m = REDACTED_GROUP_AT_END.search(str(prev))
        hidden = WS.sub(" ", str(comment)).strip()
        if not m or not hidden:
            continue
        tag = BeautifulSoup("", "lxml").new_tag("twi-redact")
        tag["data-reveal"] = _fill_redaction(m.group(1), hidden)
        tag.string = m.group(1)
        before = NavigableString(str(prev)[: m.start()])
        prev.replace_with(before)
        before.insert_after(tag)
        if m.group(2):
            tag.insert_after(NavigableString(m.group(2)))
        comment.extract()


def _plain(text: str) -> list:
    """Text nodes with look-alike "font" characters turned into plain letters."""
    return [Text(t, style) for t, style in normalize_styled(text)]


def _text_nodes(text: str) -> list:
    """Split text into Text and (comment-less) Redaction nodes."""
    if "█" not in text:
        return _plain(text)
    out: list = []
    pos = 0
    for m in REDACTED_RUN.finditer(text):
        if m.start() > pos:
            out.extend(_plain(text[pos:m.start()]))
        out.append(Redaction(m.group(0)))
        pos = m.end()
    if pos < len(text):
        out.extend(_plain(text[pos:]))
    return out


def _strip_junk(root: Tag) -> None:
    _mark_redactions(root)
    for node in root.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    for tag in root.find_all(True):
        if tag.decomposed:
            continue
        if tag.name in DROP_TAGS or DROP_CLASSES.search(_classes(tag)):
            tag.decompose()


def _inlines(node: Tag) -> list:
    out: list = []
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            text = WS.sub(" ", str(child))
            if text:
                out.extend(_text_nodes(text))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name == "br":
            out.append(Break())
        elif name == "twi-redact":
            out.append(Redaction(child.get_text(), child.get("data-reveal") or None))
        elif name in EM_TAGS or (name == "span" and EM_CLASSES & set(child.get("class") or [])):
            kids = _inlines(child)
            if kids:
                out.append(Em(kids))
        elif name in STRONG_TAGS:
            kids = _inlines(child)
            if kids:
                out.append(Strong(kids))
        elif name == "a":
            kids = _inlines(child)
            href = (child.get("href") or "").strip()
            if not plain_text(kids).strip():
                continue  # image links, empty anchors
            if href and not re.search(r"\.(jpe?g|png|gif|webp)(\?.*)?$", href, re.I):
                out.append(Link(href, kids))
            else:
                out.extend(kids)
        else:  # span, u, sup, font, block tags nested in inline context...
            out.extend(_inlines(child))
    return out


def _has_block_child(tag: Tag) -> bool:
    return any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in tag.descendants)


def _collect(node: Tag, out: list) -> None:
    pending: list = []  # loose inline content at block level

    def flush():
        if pending:
            frag = BeautifulSoup("", "lxml").new_tag("p")
            for item in pending:
                frag.append(item)
            out.append(Para(_inlines(frag)))
            pending.clear()

    for child in list(node.children):
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            if str(child).strip():
                pending.append(child.extract())
            continue
        if not isinstance(child, Tag):
            continue
        if child.name == "hr":
            flush()
            out.append(Rule())
        elif child.name in LEAF_BLOCKS:
            flush()
            if _has_block_child(child) and child.name not in {"pre"}:
                _collect(child, out)
            else:
                out.append(Para(_inlines(child)))
        elif child.name in BLOCK_TAGS:
            flush()
            if _has_block_child(child):
                _collect(child, out)
            else:
                out.append(Para(_inlines(child)))
        elif child.name == "br":
            continue
        else:
            pending.append(child.extract())
    flush()


def html_to_blocks(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    root = soup.find("article", class_="twi-article") or soup.body or soup
    _strip_junk(root)
    blocks: list = []
    _collect(root, blocks)
    return blocks


# --- classification helpers -------------------------------------------------


def _text(block) -> str:
    if isinstance(block, Para):
        return WS.sub(" ", plain_text(block.inlines, raw_redactions=True)).strip()
    return ""


def _is_blank(block) -> bool:
    return isinstance(block, Para) and not _text(block)


def _is_separator(block) -> bool:
    if isinstance(block, Rule):
        return True
    t = _text(block)
    return bool(t) and bool(SEPARATOR.match(t)) and len(t.replace(" ", "")) >= 2


def _is_nav(block) -> bool:
    t = _text(block)
    if not t or not NAV_WORDS.search(t):
        return False
    return not NAV_WORDS.sub("", t).strip(" |·•-–—")


def _links(inlines: list) -> list[Link]:
    out = []
    for n in inlines:
        if isinstance(n, Link):
            out.append(n)
        elif isinstance(n, (Em, Strong)):
            out.extend(_links(n.children))
    return out


def _all_bold(inlines: list) -> bool:
    """True if every non-blank text run sits inside <strong>."""
    def walk(nodes, bold):
        for n in nodes:
            if isinstance(n, Text):
                if n.text.strip() and not bold:
                    return False
            elif isinstance(n, Strong):
                if not walk(n.children, True):
                    return False
            elif isinstance(n, (Em, Link)):
                if not walk(n.children, bold):
                    return False
        return True
    return walk(inlines, False)


CHAPTER_URL = re.compile(r"^https://wanderinginn\.com/\d{4}/\d{2}/\d{2}/")


def _is_link_only(block) -> bool:
    """A promo paragraph: a bare URL, or only links pointing away from the story.

    Links to other chapters are story text (Solstice's "—Saw." links to the next
    part), so they never count.
    """
    if not isinstance(block, Para):
        return False
    t = _text(block)
    if not t:
        return False
    if URLISH.match(t):
        return True
    links = _links(block.inlines)
    if not links or any(CHAPTER_URL.match(norm_url(l.href) or "") for l in links):
        return False
    rest = WS.sub(" ", t)
    for link in links:
        rest = rest.replace(WS.sub(" ", plain_text(link.children, raw_redactions=True)).strip(), "", 1)
    rest = rest.strip()
    # Nothing but links, or a short label like "Android:" / "Ko-Fi:" before them.
    return not rest or (len(rest) <= 30 and rest.endswith(":"))


def _wrapped_group(blocks: list, i: int) -> int:
    """If blocks[i] opens a bracketed announcement, return its length (else 0)."""
    t = _text(blocks[i])
    if not t or t[0] not in PAIRS:
        return 0
    closer = PAIRS[t[0]]
    for j in range(i, min(i + 6, len(blocks))):
        tj = _text(blocks[j]).rstrip(" .")
        if not tj:
            return 0
        if tj.endswith(closer):
            n = j - i + 1
            if t[0] != "(":
                # "[Skill]" and "<Query>" lines are story text; require announcement traits.
                group = blocks[i:j + 1]
                joined = " ".join(_text(b) for b in group)
                long = len(joined) >= 150
                linked = any(_links(b.inlines) for b in group)
                bold = all(_all_bold(b.inlines) for b in group)
                worded = bool(ANNOUNCE_WORDS.search(joined))
                if not (n > 1 or long or linked or bold or worded):
                    return 0
            return n
    return 0


# --- cleaning passes --------------------------------------------------------


def _remove_nav(blocks: list) -> list:
    out = [b for b in blocks if not _is_nav(b)]
    while out and (isinstance(out[-1], Rule) or _is_blank(out[-1])):
        out.pop()
    return out


def _note_end(blocks: list, i: int) -> int:
    """End index of a note starting at i: up to the next blank line or separator."""
    j = i + 1
    while j < len(blocks) and not _is_blank(blocks[j]) and not _is_separator(blocks[j]):
        j += 1
    return j


def _leading_notes(blocks: list) -> tuple[int, list[tuple[int, int]]]:
    """Where the story starts after any opening announcements, plus the spans of
    opening author's notes among them (kept when notes are kept)."""
    i, notes = 0, []
    while i < len(blocks):
        b = blocks[i]
        if _is_blank(b) or isinstance(b, Rule):
            i += 1
        elif AUTHOR_NOTE.match(_text(b)):
            end = _note_end(blocks, i)
            notes.append((i, end))
            i = end
        elif n := _wrapped_group(blocks, i):
            i += n
        elif _is_link_only(b):
            i += 1
        else:
            break
    return i, notes


def _leading_end(blocks: list) -> int:
    """Index of the first story paragraph after any opening announcements."""
    return _leading_notes(blocks)[0]


def _strip_leading(blocks: list, res: CleanResult, keep_notes: bool = False) -> list:
    """Remove opening announcements (promos, bracketed notices). In keep-notes
    mode an opening "Author's Note" paragraph stays."""
    end, notes = _leading_notes(blocks)
    kept = [b for a, z in notes for b in blocks[a:z]] if keep_notes else []
    kept_ids = {id(b) for b in kept}
    removed = [b for b in blocks[:end]
               if id(b) not in kept_ids and not _is_blank(b) and not isinstance(b, Rule)]
    if removed:
        text = " ".join(_text(b) for b in removed)
        res.log.append(f"removed opening announcement: {text[:160]}{'…' if len(text) > 160 else ''}")
        if CW_WORDS.search(text):
            res.content_warning = True
    _find_alternates([b for b in blocks[:end] if not _is_blank(b)], res)
    return kept + blocks[end:]


def _find_alternates(removed: list, res: CleanResult) -> None:
    for b in removed:
        if not isinstance(b, Para):
            continue
        t = _text(b)
        pw = PASSWORD_HINT.search(t)
        for link in _links(b.inlines):
            url = norm_url(link.href)
            if not url:
                continue
            ctx = (t + " " + url).lower()
            if "trigger-free" in ctx or "trigger free" in ctx:
                kind = "trigger-free"
            elif "summary" in url:
                kind = "summary"
            else:
                continue
            res.alternates.setdefault(kind, (url, pw.group(1) if pw else None))


def _closing_group_start(blocks: list, end: int) -> int | None:
    """Start of a bold or linked bracketed group ending just before `end`."""
    for start in range(end - 1, max(-1, end - 7), -1):
        if _wrapped_group(blocks, start) == end - start:
            group = blocks[start:end]
            if any(_links(g.inlines) for g in group) or all(_all_bold(g.inlines) for g in group):
                return start
    return None


def _strip_trailing(blocks: list, res: CleanResult) -> list:
    """Remove closing announcements, e.g. Solstice's "(Before going to next chapter…)"."""
    end = len(blocks)
    removed: list = []
    while end > 0:
        b = blocks[end - 1]
        if _is_blank(b) or isinstance(b, Rule):
            end -= 1
            continue
        if _is_link_only(b):
            removed.insert(0, b)
            end -= 1
            continue
        start = _closing_group_start(blocks, end)
        if start is None:
            break
        removed[:0] = blocks[start:end]
        end = start
    if removed:
        text = " ".join(_text(b) for b in removed)
        res.log.append(f"removed closing announcement: {text[:160]}{'…' if len(text) > 160 else ''}")
    return blocks[:end]


CREDIT_URL = re.compile(r"https?://|www\.|\b[\w-]+\.(com|art|net|org|app|social|se)/", re.I)
CREDIT_BY = re.compile(r"\bby\b", re.I)


def _is_credit(block) -> bool:
    """A fan-art credit line: "Erin by Brack!" or "Ko-Fi: https://ko-fi.com/brack"."""
    if not isinstance(block, Para):
        return False
    t = _text(block)
    if not t:
        return True
    if CREDIT_URL.search(t) and len(t) < 200:
        return True
    return bool(CREDIT_BY.search(t)) and len(t) < 140 and t.count(". ") <= 1


def _strip_credits(blocks: list, res: CleanResult, after: int | None) -> list:
    """Cut the trailing run of art-credit lines (the gallery images are already gone).

    `after`: index where the author's note starts, or None if there is none, in
    which case the run must contain a URL so a story's last line is never cut.
    """
    start = len(blocks)
    floor = (after + 1) if after is not None else 0
    while start > floor and (_is_credit(blocks[start - 1]) or isinstance(blocks[start - 1], Rule)):
        start -= 1
    run = blocks[start:]
    if not any(_text(b) for b in run):
        return blocks
    if after is None and not any(CREDIT_URL.search(_text(b)) for b in run):
        return blocks
    res.log.append(f"removed {sum(1 for b in run if _text(b))} fan-art credit lines")
    return blocks[:start]


def _find_author_note(blocks: list) -> int | None:
    for i, b in enumerate(blocks):
        if AUTHOR_NOTE.match(_text(b)) and i >= len(blocks) * 0.5:
            return i
    return None


def _drop_chars(inlines: list, n: int) -> list:
    """Remove the first n characters of text from an inline tree."""
    out = []
    for node in inlines:
        if n <= 0:
            out.append(node)
        elif isinstance(node, Text):
            if len(node.text) <= n:
                n -= len(node.text)
            else:
                out.append(replace(node, text=node.text[n:]))
                n = 0
        elif isinstance(node, Break):
            n -= 1
        elif isinstance(node, Redaction):
            out.append(node)
            n = 0
        else:
            size = len(plain_text(node.children))
            if size <= n:
                n -= size
            else:
                out.append(type(node)(*([node.href] if isinstance(node, Link) else []), _drop_chars(node.children, n)))
                n = 0
    return out


def _mark_author_note(blocks: list, res: CleanResult) -> list:
    """Keep-notes mode: put the closing author's note under its own heading."""
    i = _find_author_note(blocks)
    if i is None:
        return _strip_credits(blocks, res, None)
    blocks = _strip_credits(blocks, res, i)
    first = blocks[i]
    m = re.match(rf"\s*{NOTE_LABEL}\s*[:.\-–—]?\s*", plain_text(first.inlines), re.I)
    rest = _trim(_drop_chars(first.inlines, m.end() if m else 0))
    note = [Rule(), Heading(1, "Author’s Note")] + ([Para(rest)] if plain_text(rest).strip() else [])
    return blocks[:i] + note + blocks[i + 1:]


def _strip_author_note(blocks: list, res: CleanResult) -> list:
    for i, b in enumerate(blocks):
        if not AUTHOR_NOTE.match(_text(b)):
            continue
        if i >= len(blocks) * 0.5:
            res.log.append(f"removed author's note and everything after it ({len(blocks) - i} paragraphs)")
            return blocks[:i]
        end = _note_end(blocks, i)
        res.log.append(f"removed a mid-chapter author's note: {_text(b)[:120]}")
        return blocks[:i] + _strip_author_note(blocks[end:], res)
    return blocks


def _normalise(blocks: list, chapter_marks: bool) -> list:
    out: list = []
    for b in blocks:
        if _is_separator(b):
            if out and not isinstance(out[-1], Rule):
                out.append(Rule())
            continue
        if _is_blank(b):
            continue
        if chapter_marks and isinstance(b, Para) and CHAPTER_MARK.match(_text(b)):
            if out and isinstance(out[-1], Rule):
                out.pop()
            out.append(Heading(1, _text(b).title()))
            continue
        if isinstance(b, Para):
            b = Para(_trim(b.inlines))
        out.append(b)
    while out and isinstance(out[-1], Rule):
        out.pop()
    return out


def _trim(inlines: list) -> list:
    """Strip leading/trailing whitespace and line breaks from a paragraph."""
    inl = list(inlines)
    while inl and (isinstance(inl[0], Break) or (isinstance(inl[0], Text) and not inl[0].text.strip())):
        inl.pop(0)
    while inl and (isinstance(inl[-1], Break) or (isinstance(inl[-1], Text) and not inl[-1].text.strip())):
        inl.pop()
    if inl and isinstance(inl[0], Text):
        inl[0] = replace(inl[0], text=inl[0].text.lstrip())
    if inl and isinstance(inl[-1], Text):
        inl[-1] = replace(inl[-1], text=inl[-1].text.rstrip())
    return inl


def clean(html: str, *, keep_notes: bool = False, chapter_marks: bool = False) -> CleanResult:
    """Clean one chapter's content HTML.

    chapter_marks: turn standalone "Chapter N" paragraphs into headings (Griefman).
    """
    res = CleanResult(blocks=[])
    blocks = _remove_nav(html_to_blocks(html))
    blocks = _strip_leading(blocks, res, keep_notes)
    if keep_notes:
        blocks = _mark_author_note(blocks, res)
    else:
        blocks = _strip_author_note(blocks, res)
        blocks = _strip_trailing(blocks, res)
        blocks = _strip_credits(blocks, res, None)
    blocks = _normalise(blocks, chapter_marks)
    if res.content_warning:
        blocks.insert(0, Para([Em([Text(CONTENT_WARNING_TEXT)])]))
    res.blocks = blocks
    return res
