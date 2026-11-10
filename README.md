# twi

Download [The Wandering Inn](https://wanderinginn.com) as clean, screen-reader-friendly
Markdown or EPUB files.

- Single chapters → Markdown, with the author's notes kept under an "Author's Note" heading.
- Whole volumes → EPUB, with the author's notes and announcements removed.
- Gallery images, fan-art credits and Previous/Next links are always removed.
- The author's dash separators (`——`, `—-`) become a real separator: `***` in Markdown,
  `<hr/>` in EPUB.
- Links between chapters stay inside the book. For example, Solstice Pt. 3's "Changed." link
  jumps to Pt. 4 in the EPUB instead of opening the website. Links to chapters that aren't in
  the file become plain text.
- Tales of Innworld and other image-only or announcement posts are left out of volumes.
- Blacked-out text (`███` in 7.25, 7.50) reads as "[redacted]" instead of "full block full
  block". Where the page hides the original words, they go in a footnote: a pop-up link in the
  EPUB, a `[^1]` footnote at the end of the chapter in Markdown.
- "Fancy font" letters become plain letters a screen reader can say. This covers small capitals
  for gods' voices (`Dᴇᴀᴛʜ ʜᴀs ᴄᴏᴍᴇ` → "Death has come"), superscript fine print, maths-font
  digits, and upside-down text (10.56 F). In the EPUB, small caps and superscripts still look
  the same.

## Install

Needs [uv](https://docs.astral.sh/uv/).

```sh
uv tool install /Users/jt/dev/twi     # puts `twi` on your PATH
# or, from this folder, without installing:
uv run twi --help
```

## Usage

```sh
twi list                        # volumes, the Volume 1 archive, and Griefman
twi list 7                      # chapters in Volume 7

twi chapter "10.78 RV"          # one chapter as Markdown -> "10.78 RV.md"
twi chapter 8.31 "solstice pt 3" latest
twi https://wanderinginn.com/2023/11/28/9-68/   # any chapter by URL

twi volume 7                    # "The Wandering Inn - Volume 7.epub"
twi volume 7 --format md        # a folder of numbered Markdown files
twi volume 7 --format md --single-file
twi volume archive              # the original 2016 Volume 1

twi book griefman               # Griefman as one EPUB, split by its own chapters
twi book griefman --format md   # ...or as one Markdown file
```

Chapter titles are matched loosely: `solstice pt 3` finds "Solstice (Pt. 3)". If a title matches
several chapters, use the full title or the URL.

### Options

| Option | Effect |
|---|---|
| `--format md` / `--format epub` | Change the output format. |
| `-o DIR`, `--output DIR` | Where to write files (default: the current folder). |
| `--single-file` | With `--format md`, write a volume as one file instead of a folder. |
| `--keep-notes` / `--no-notes` | Keep or remove author's notes and announcements. By default, `chapter` keeps them; `volume` and `book` remove them. |
| `--password PW` | A password to try on locked chapters. Can be given more than once. |
| `--skip-locked` | Skip locked chapters without asking. |
| `--trigger-free` | Where a chapter has a trigger-free version (9.68), download that instead. |
| `--include-extras` | Keep Tales of Innworld and other non-story posts in volumes. |
| `--refresh` | Download pages again instead of using the cache. |

## Locked chapters

Some chapters are Patreon-locked, including the newest chapter and many rewritten Volume 1–2
chapters, which have a password field on the site. When `twi` meets one, it:

1. tries the passwords you gave with `--password` or the `TWI_PASSWORD` environment variable,
   then any password you've already typed in this run;
2. otherwise asks: `"10.79 RVP" is Patreon-locked (Jar of Acid tier). Password (blank to skip):`.
   A wrong password asks again. A blank answer skips that chapter and every other chapter
   behind the same lock for the rest of the run, so you aren't asked 50 times.

Skipped chapters are listed at the end. With `--skip-locked`, or when not run in a terminal,
locked chapters are skipped without asking.

**Wrong passwords get you blocked.** The site's firewall blocks a connection from locked pages
after wrong password attempts, with a "WP Remote Firewall: Blocked because of Malicious
Activities" page. Other pages keep working. To avoid this, `twi` remembers which password works
for each Patreon tier and never sends a password again for a tier where it already failed. If
you do get blocked, `twi` stops and says so. Wait a while before trying again. Everything
already downloaded is cached, so the rerun is quick.

Some extra pages, such as 9.68's trigger-free version, use a password printed in the chapter
itself. `twi` reads that password and uses it automatically.

## Progress messages

Progress goes to standard error as plain lines (`[3/95] 7.02`), with no progress bars or
colour. Each line also says what was removed from a chapter, so nothing disappears silently.

## Cache

Unlocked chapter pages are cached in `~/.cache/twi`. The table of contents is refreshed every
hour. Locked pages are never cached. Delete the folder, or pass `--refresh`, to download
everything again.
