# twi: notes for Claude

A CLI that downloads The Wandering Inn (wanderinginn.com) as Markdown or EPUB. The user reads
with a **screen reader**. That drives these choices: minimal Markdown escaping (backslashes get
read aloud), plain-line progress output (no bars or ANSI), real headings for navigation, and
`<hr/>` / `***` for scene breaks.

Keep this file up to date when the site or the rules change.

## Commands

```sh
uv run pytest -q          # unit tests; offline HTML fixtures shaped like the real pages
uv run twi --help
uv run twi chapter "10.78 RV" -o out
uv run twi volume 7 -o out             # 95 chapters, about 2 min uncached (1 s between requests)
```

To audit the cleaner over many chapters, write a script that calls `Site().fetch()` and
`clean()` and prints the log plus the first and last blocks of each chapter. Pages are cached in
`~/.cache/twi`, so repeat runs are fast.

## Releasing

CI (`.github/workflows/ci.yml`) runs the tests on Python 3.11–3.13 on Linux, macOS and Windows
for every push and PR, builds the wheel, runs `twi --version` from it, and checks
`CHANGELOG.md` has an entry for the current version.

Published to PyPI as `twi-scraper` (command `twi`). `.github/workflows/publish.yml` runs on
every push to `main`; if `v<version>` has no GitHub release yet, it publishes to PyPI and
creates the release, with notes from that version's `CHANGELOG.md` section
(`.github/changelog_notes.py`). So: record user-visible changes under `## [Unreleased]` as you
make them; to release, rename it to `## [X.Y.Z] - date`, bump `pyproject.toml`, push. Don't
rename `publish.yml` or the `pypi` environment: PyPI's trusted publisher is tied to them.

## Layout

- `src/twi/site.py`: HTTP with a 1 s delay, JSON page cache, TOC and archive parsing, lock
  detection, both unlock flows, `BOOKS` (Griefman).
- `src/twi/clean.py`: HTML → blocks. All the stripping rules live here.
- `src/twi/model.py`: inline and block node types, `Chapter`, `norm_url`.
- `src/twi/markdown.py`, `src/twi/epub.py`: writers. Each takes a resolver: a site URL inside
  the output becomes an internal link, any other site URL becomes plain text, and external
  links are kept.
- `src/twi/cli.py`: argparse, `Passwords` (per-lock memory, then prompt), `Builder`, Griefman
  flattening.
- `src/twi/unistyle.py`: look-alike "font" Unicode → plain letters, tagged with the style they
  had ("sc" or "sup") so the EPUB can still show it.

## User's requirements (decided)

- `chapter` defaults to Markdown and **keeps author's notes**, under an "Author's Note" heading.
  `volume` and `book` default to EPUB and **strip notes**. `--keep-notes` / `--no-notes` override.
- Gallery images, fan-art credits and nav links are always removed.
- Tales of Innworld are excluded from volumes, along with "Crossover Comic" and "Announcement"
  posts (`EXTRA_TITLES`). `--include-extras` keeps them.
- Any wanderinginn.com URL can be downloaded directly (`twi <url>`); lock rules still apply.
- Links between chapters must stay inside the book, never jump to the website.
- Redacted text must not read as "full block…". It reads as `[redacted]`, and the hidden
  original stays "sort of hidden" in a footnote (EPUB `noteref` pop-up, Markdown `[^n]`).
- Look-alike "font" letters (small caps, superscripts, upside-down) must read as plain words.

## Site facts (verified 2026-11-10)

- TOC: `/table-of-contents/`. Volumes are `div.volume-wrapper#vol-N`; entries are
  `div.chapter-entry .body-web a`. 842 entries.
- Chapter text: `article.twi-article` inside
  `[data-widget_type="theme-post-content.default"] .elementor-widget-container`. "Page"-type
  posts (e.g. `/9-68-trigger-free/`) have **no** `twi-article`; the text sits directly in that
  container.
- The "Chapter Gallery" widget is outside the content container, so it is never picked up.
- Separators are paragraphs of `——` or `—-` between `&nbsp;` paragraphs.
- The end of a chapter is: author's note → fan-art images and credits ("X by Y!",
  "Ko-Fi: url") → `<hr>` → Previous/Next paragraph. Older chapters (Volume 7 era) label the
  note **"After Chapter Thoughts:"**.
- Openings can carry announcements: bold paragraphs wrapped in `()`, `[]`, `{}` or `<>`
  (9.68 uses all four), multi-paragraph `[…]` (10.10 E), promo lines like "Android: url"
  (7.46 K), a cover image, and shop links (Griefman Pt. 1).
- Story text that looks like announcements must survive: `[Skill – X obtained!]`,
  `<Priority Query…>` lines (10.27 GMG), and link-only paragraphs that link to the next part
  (Solstice Pt. 3–8: "Changed.", "—Saw.").
- Solstice Pt. 3 ends with a bold "(Before going to next chapter, read Solstice Pt. 4-9…)" note.
- **Patreon lock**: `div.patreon-protected-post`. A JS-injected form POSTs `hybrid_pass` to the
  chapter URL (the session needs `PHPSESSID`). A wrong password renders
  `HYBRID_BAD_PASSWORD = "1"`. Applies to the newest chapter, many rewritten Volume 1–2 chapters
  (1.01–1.10, 2.00–2.10…), and **every archive chapter checked**.
- **WordPress lock**: `input[name=post_password]`. POST `post_password` to
  `/wp-login.php?action=postpass&wpe-login=true`, then GET with a **cache-busting query**
  (`?nc=…`). Without it the CDN serves the locked copy even when the cookie is valid. Used by
  `/9-68-trigger-free/` and `/9-68-summary/`. Their password, `traumaFree`, is printed in 9.68's
  own announcement, and `clean._find_alternates` extracts it.
- Volume 1 archive: `/vol-1-archive/`, about 65 dated 2016–2017 links. Rewrite links (`/rw1-…`)
  are skipped.
- Griefman: 3 parts, not in the TOC, chained by Next Chapter links (`griefman-pt-1..3`). The
  book's own chapters are standalone "Chapter N" paragraphs; Pt. 1 opens with "Foreword:".
  Output is regrouped by those chapters.
- **Redactions** (7.25 has 48, 7.50 has 1) are literal `█` characters followed by an HTML
  comment holding the original: `███<!--six-->`, `███, ███<!--one, two-->`,
  `█i█g█<!--wns-->` (one letter per █, so partial words rebuild to "wings").
  `clean._mark_redactions` pairs them before comments are stripped. Gallery markup also has
  comments (`<!-- close group -->`); they're ignored because no █ precedes them. The cleaner's
  heuristics read redactions as raw `█` (`plain_text(raw_redactions=True)`), because the
  "[redacted]" display text looks like a bracketed announcement.
- **Look-alike letters** found by scanning all of Volume 10:
  - small capitals (`ᴀ ᴇ ᴛ ꜱ ꜰ ɢ ɪ ɴ ʀ ʜ ʟ ʏ ʙ`, plus Cyrillic `ғ`) in 10.31, 10.35, 10.56,
    10.58, 10.66, 10.70, 10.71 and Interlude – Liska;
  - superscript modifier letters in Goblin Days (Pt. 7);
  - a maths digit `𝟦` in 10.66;
  - **upside-down** passages in 10.56 F. Those also flip plain letters (`n/u b/q p/d M/W`) and
    punctuation (`˙ ┴ [ ]`, word-final `’` = comma), so a run with 3+ turned letters is flipped
    as a whole passage.

  Left alone on purpose: `™` (used for jokes, read fine), the kaomoji `•̀ᴗ-`, mirrored text in
  plain letters (10.56 "eht llits uoy erA"), and `DrakeScript2` font spans (The Roots, 10.27),
  whose underlying text is normal English.
- **Firewall**: after wrong password attempts, locked pages return 403 with
  "WP Remote Firewall: Blocked because of Malicious Activities" for that IP. Other pages stay
  200. My own probing triggered it on 2026-11-10 (wrong `post_password` variants plus a
  wrong-password prompt test). `Site._request` raises `SiteBlocked`, and the CLI stops. Never
  test with wrong passwords against the live site; use the `FakeSite` in
  `tests/test_text_effects.py`.
- The Patreon lock screen names its tier ("Minimum tier: Blue Fruit Juice or higher"). Passwords
  are presumably per tier, so `Passwords` keys its memory by `Page.lock_key`.

## Unverified

- **A successful Patreon `hybrid_pass` unlock.** I have no password. The flow is built from the
  site's form and the wrong-password path works. If the user reports a failure, inspect the
  POST response. It may redirect, or need the `nc` GET (which `Site.unlock` already falls back
  to).
- Whether unlocked archive chapters use `article.twi-article`. If not, the container fallback
  in `parse_page` should still find the text.
