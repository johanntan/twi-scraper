"""Turn "fancy font" Unicode back into plain letters a screen reader can say.

The author fakes typography with look-alike characters (verified in Volume 10):

- small capitals for gods' voices: "Dᴇᴀᴛʜ ʜᴀs ᴄᴏᴍᴇ ғᴏʀ ʏᴏᴜ" (10.31, 10.35, 10.56, ...)
- superscript fine print: "Effect™ᴺᵒ ᴿᶦᵍʰᵗˢ ᴿᵉˢᵉʳᵛᵉᵈ" (Goblin Days Pt. 7)
- upside-down text: "Sɐʇɐɹ: ˥ǝʍpbnᴉll¿" = "Satar: Lewdquill?" (10.56 F)
- maths digits: "ᴘᴀɢᴇ 𝟦" (10.66 Pt. 1)

Screen readers spell these out ("latin letter small capital e"). `normalize`
returns plain text split into segments tagged with the style they had, so the
EPUB can still show small caps / superscript visually.
"""

from __future__ import annotations

import re
import unicodedata

SMALL_CAPS = {
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e", "ꜰ": "f", "ɢ": "g", "ʜ": "h",
    "ɪ": "i", "ᴊ": "j", "ᴋ": "k", "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o", "ᴘ": "p",
    "ʀ": "r", "ꜱ": "s", "ᴛ": "t", "ᴜ": "u", "ᴠ": "v", "ᴡ": "w", "ʏ": "y", "ᴢ": "z",
}
# Look-alikes from other alphabets, only trusted inside a small-caps word.
SMALL_CAPS_EXTRA = {"ғ": "f", "ǫ": "q", "ѕ": "s", "х": "x", "ᴉ": "i"}

TURNED = {
    "ɐ": "a", "ɔ": "c", "ǝ": "e", "ɟ": "f", "ƃ": "g", "ɥ": "h", "ᴉ": "i", "ɾ": "j",
    "ʞ": "k", "ɯ": "m", "ɹ": "r", "ʇ": "t", "ʌ": "v", "ʍ": "w", "ʎ": "y",
    "∀": "A", "Ɔ": "C", "Ǝ": "E", "Ⅎ": "F", "⅁": "G", "˥": "L", "Ԁ": "P",
    "⊥": "T", "∩": "U", "Λ": "V", "⅄": "Y", "¿": "?", "¡": "!",
}
# In upside-down words these ordinary letters stand for their mirror image.
TURNED_SWAP = {"n": "u", "u": "n", "b": "q", "q": "b", "p": "d", "d": "p"}
# Extra swaps used only when a whole passage is upside down (10.56 F: "the Morld[˙").
TURNED_PASSAGE = {"M": "W", "W": "M", "˙": ".", "┴": "T", "[": "]", "]": "["}
# Turned characters that never occur in normal English text; one of these marks a word as turned.
TURNED_MARKERS = set(TURNED) - {"¿", "¡"}

# Modifier/superscript letters and "<font>"/fullwidth/circled characters.
_COMPAT_RANGES = re.compile(
    "[ʰ-˿ᴬ-ᶿⁱ-ₜ"  # modifier letters, superscript/subscript letters
    "\U0001d400-\U0001d7ff"                      # mathematical alphanumerics
    "！-～①-⓿]"                # fullwidth, enclosed alphanumerics
)
_SUPER_RANGES = re.compile("[ʰ-˿ᴬ-ᶿⁱ-ₜ]")
_KEEP = set("™®©℠°")


def _compat(ch: str) -> str:
    if ch in _KEEP or not _COMPAT_RANGES.match(ch):
        return ch
    out = unicodedata.normalize("NFKC", ch)
    # NFKC turns "ᶦ" into small-capital "ɪ"; finish the job.
    return "".join(SMALL_CAPS.get(c, c) for c in out)


def _word(word: str) -> list[tuple[str, str | None]]:
    """Normalise one whitespace-free token; return styled segments."""
    if any(c in TURNED_MARKERS for c in word):
        return [("".join(TURNED.get(c) or TURNED_SWAP.get(c) or c for c in word), None)]
    if any(c in SMALL_CAPS for c in word):
        table = {**SMALL_CAPS, **SMALL_CAPS_EXTRA}
        return [("".join(table.get(c, _compat(c)) for c in word), "sc")]
    segs: list[tuple[str, str | None]] = []
    for c in word:
        style = "sup" if _SUPER_RANGES.match(c) and c not in _KEEP else None
        mapped = _compat(c)
        if segs and segs[-1][1] == style:
            segs[-1] = (segs[-1][0] + mapped, style)
        else:
            segs.append((mapped, style))
    return segs


def _unturn_passage(text: str) -> str:
    """Flip a whole upside-down passage back, plain-looking words included."""
    def word(m: re.Match) -> str:
        w = m.group(0)
        out = "".join(TURNED.get(c) or TURNED_PASSAGE.get(c) or TURNED_SWAP.get(c) or c for c in w)
        # A flipped comma looks like an apostrophe at the end of a word.
        return out[:-1] + "," if out.endswith("’") else out
    return re.sub(r"\S+", word, text)


def needs_work(text: str) -> bool:
    return any(
        c in SMALL_CAPS or c in TURNED_MARKERS or (_COMPAT_RANGES.match(c) and c not in _KEEP)
        for c in text
    )


def normalize(text: str) -> list[tuple[str, str | None]]:
    """Plain-letter version of `text` as (text, style) segments; style is None, "sc" or "sup"."""
    text = unicodedata.normalize("NFC", text)
    if not needs_work(text):
        return [(text, None)]
    if sum(c in TURNED_MARKERS for c in text) >= 3:
        return [(_unturn_passage(text), None)]
    segs: list[tuple[str, str | None]] = []
    tokens = re.split(r"(\s+)", text)
    for i, tok in enumerate(tokens):
        if not tok:
            continue
        if tok.isspace():
            # A space between two styled words belongs to the styled run.
            prev = segs[-1][1] if segs else None
            nxt = _word(tokens[i + 1])[0][1] if i + 1 < len(tokens) and tokens[i + 1] else None
            parts = [(tok, prev if prev == nxt else None)]
        else:
            parts = _word(tok)
        for t, s in parts:
            if s == "sup" and segs and segs[-1][1] != "sup" and segs[-1][0][-1:].isalnum():
                t = " " + t  # "Effectᴺᵒ ᴿᶦᵍʰᵗˢ" -> "Effect No Rights"
            if segs and segs[-1][1] == s:
                segs[-1] = (segs[-1][0] + t, s)
            else:
                segs.append((t, s))
    return [(_sentence_case(t) if s == "sc" else t, s) for t, s in segs]


def _sentence_case(text: str) -> str:
    """All-small-caps passages have no capitals at all; restore sentence starts.

    Passages that already had real capitals ("Dᴇᴀᴛʜ ʜᴀs ᴄᴏᴍᴇ") are left alone.
    Proper names inside all-small-caps text stay lowercase: there's no way to know them.
    """
    if any(c.isupper() for c in text):
        return text
    return re.sub(r"(^|[.!?…]\s+)([^\w\s]*)(\w)", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)
