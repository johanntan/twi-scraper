"""Command-line interface: `twi list | chapter | volume | book`."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import time
from pathlib import Path

from . import __version__
from .clean import CONTENT_WARNING_TEXT, clean
from .epub import write_epub
from .markdown import chapter_markdown, folder_resolver, single_file
from .model import Chapter, Em, Heading, Para, Text, norm_url, plain_text
from .site import BOOKS, ChapterRef, Site, SiteBlocked, SiteError, log

TRIGGER_FREE_NOTE = (
    "This is the trigger-free version of the chapter: the most disturbing scenes "
    "are replaced by a summary."
)


class Passwords:
    """Known passwords, plus prompting for new ones.

    The site's firewall blocks a connection after wrong password attempts, so
    every attempt counts: a password that worked for a lock (Patreon tier) is
    reused, and one that failed for a lock is never sent for it again.
    """

    WRONG_PAUSE = 3.0  # seconds after a wrong password typed at the prompt

    def __init__(self, given: list[str], skip_locked: bool):
        self.known: list[str] = []
        for p in given + [os.environ.get("TWI_PASSWORD", "")]:
            self.add(p)
        self.interactive = not skip_locked and sys.stdin.isatty()
        self.skipped: list[str] = []
        self.works: dict[str, str] = {}  # lock key -> password
        self.failed: dict[str, set[str]] = {}  # lock key -> passwords that failed
        self.gave_up: set[str] = set()  # lock keys the user chose to skip

    def add(self, pw: str | None) -> None:
        if pw and pw not in self.known:
            self.known.append(pw)

    def _try(self, site: Site, page, pw: str):
        key = page.lock_key
        if pw in self.failed.get(key, set()):
            return None
        unlocked = site.unlock(page, pw)
        if unlocked:
            self.works[key] = pw
            self.add(pw)
        else:
            self.failed.setdefault(key, set()).add(pw)
        return unlocked

    def _skip(self, title: str, why: str) -> None:
        log(f"  skipped {title}: {why}")
        self.skipped.append(title)

    def fetch(self, site: Site, url: str, title: str):
        """Fetch a page, unlocking it if needed. Returns None if skipped."""
        page = site.fetch(url)
        if not page.lock:
            return page
        key = page.lock_key
        kind = "Patreon-locked" if page.lock == "patreon" else "password-protected"
        if page.tier:
            kind += f" ({page.tier} tier)"
        candidates = [self.works[key]] if key in self.works else self.known
        for pw in candidates:
            unlocked = self._try(site, page, pw)
            if unlocked:
                log(f"  unlocked {title} with a saved password")
                return unlocked
        if not self.interactive or key in self.gave_up:
            self._skip(title, kind + (" (no saved password worked)" if self.known else ""))
            return None
        while True:
            try:
                pw = getpass.getpass(f'"{title}" is {kind}. Password (blank to skip): ')
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                pw = ""
            pw = pw.strip()
            if not pw:
                # Don't ask again for other chapters behind the same lock this run.
                self.gave_up.add(key)
                self._skip(title, "no password given; other chapters behind the same lock will be skipped too")
                return None
            if pw in self.failed.get(key, set()):
                log("  that password was already wrong for this lock, try another")
                continue
            unlocked = self._try(site, page, pw)
            if unlocked:
                log(f"  unlocked {title}")
                return unlocked
            log("  wrong password, try again")
            time.sleep(self.WRONG_PAUSE)


class Builder:
    def __init__(self, site: Site, pw: Passwords, args):
        self.site = site
        self.pw = pw
        self.keep_notes = args.keep_notes
        self.trigger_free = args.trigger_free

    def chapter(self, ref: ChapterRef, chapter_marks: bool = False) -> Chapter | None:
        page = self.pw.fetch(self.site, ref.url, ref.title)
        if page is None:
            return None
        res = clean(page.content_html, keep_notes=self.keep_notes, chapter_marks=chapter_marks)
        for line in res.log:
            log(f"  {ref.title}: {line}")
        blocks = res.blocks
        alt = res.alternates.get("trigger-free")
        if alt and not self.trigger_free:
            log(f"  {ref.title}: a trigger-free version exists; use --trigger-free to download it instead")
        if alt and self.trigger_free:
            url, password = alt
            self.pw.add(password)
            alt_page = self.pw.fetch(self.site, url, f"{ref.title} (trigger-free)")
            if alt_page is not None:
                alt_res = clean(alt_page.content_html, keep_notes=self.keep_notes, chapter_marks=chapter_marks)
                blocks = [Para([Em([Text(TRIGGER_FREE_NOTE)])])] + alt_res.blocks
                log(f"  {ref.title}: using the trigger-free version")
        return Chapter(ref.title, ref.url, blocks)

    def many(self, refs: list[ChapterRef], chapter_marks: bool = False) -> list[Chapter]:
        out = []
        for i, ref in enumerate(refs, 1):
            log(f"[{i}/{len(refs)}] {ref.title}")
            ch = self.chapter(ref, chapter_marks)
            if ch is not None:
                out.append(ch)
        return out


# --- helpers ------------------------------------------------------------------


def safe_name(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", name).strip(" .")
    return name or "untitled"


def resolve_targets(site: Site, targets: list[str]) -> list[ChapterRef]:
    refs: list[ChapterRef] = []
    for t in targets:
        if re.match(r"^(https?://|www\.|wanderinginn\.com)", t, re.I):
            url = norm_url(t if "://" in t else "https://" + t)
            if url is None:
                raise SiteError(f"not a wanderinginn.com URL: {t}")
            ref = site.find_by_url(url)
            if ref is None:
                page = site.fetch(url)
                ref = ChapterRef(page.title, url)
            refs.append(ref)
            continue
        if t.lower() == "latest":
            refs.append(site.all_chapters()[-1])
            continue
        found = site.find_by_title(t)
        if not found:
            raise SiteError(f'no chapter titled "{t}" (try `twi list <volume>` or pass the URL)')
        if len(found) > 1:
            names = "; ".join(f"{c.title} (volume {c.volume})" for c in found[:10])
            raise SiteError(f'"{t}" matches several chapters: {names}. Use the full title or the URL.')
        refs.append(found[0])
    return refs


def filter_extras(refs: list[ChapterRef], include: bool) -> list[ChapterRef]:
    if include:
        return refs
    extras = [r for r in refs if r.is_extra]
    if extras:
        log(f"leaving out {len(extras)} non-story posts (use --include-extras to keep them): "
            + "; ".join(r.title for r in extras))
    return [r for r in refs if not r.is_extra]


def write_collection(title: str, chapters: list[Chapter], args, out_dir: Path) -> None:
    if not chapters:
        log("nothing to write")
        return
    if args.format == "epub":
        path = out_dir / f"{safe_name(title)}.epub"
        write_epub(path, title, chapters)
        log(f"wrote {path} ({len(chapters)} chapters)")
    elif args.single_file:
        path = out_dir / f"{safe_name(title)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(single_file(title, chapters), "utf-8")
        log(f"wrote {path} ({len(chapters)} chapters)")
    else:
        folder = out_dir / safe_name(title)
        folder.mkdir(parents=True, exist_ok=True)
        width = max(3, len(str(len(chapters))))
        names = [f"{i:0{width}d} - {safe_name(ch.title)}.md" for i, ch in enumerate(chapters, 1)]
        files = {norm_url(u) or u: name for ch, name in zip(chapters, names) for u in ch.urls()}
        resolve = folder_resolver(files)
        for ch, name in zip(chapters, names):
            (folder / name).write_text(chapter_markdown(ch, resolve), "utf-8")
        log(f"wrote {len(chapters)} files to {folder}")


def build_book(builder: Builder, site: Site, key: str) -> tuple[str, list[Chapter]]:
    spec = BOOKS[key]
    refs: list[ChapterRef] = []
    url, seen = spec["start"], set()
    while url and url not in seen and url.rstrip("/").rsplit("/", 1)[-1].startswith(spec["slug_prefix"]):
        seen.add(url)
        page = builder.pw.fetch(site, url, url)
        if page is None:
            break
        refs.append(ChapterRef(page.title, url))
        url = page.next_url
    log(f"{spec['title']}: found {len(refs)} parts")
    parts = builder.many(refs, chapter_marks=True)
    return spec["title"], flatten_by_chapter_marks(spec["title"], parts)


def flatten_by_chapter_marks(title: str, parts: list[Chapter]) -> list[Chapter]:
    """Re-split web parts at the book's own "Chapter N" headings."""
    if not any(isinstance(b, Heading) for p in parts for b in p.blocks):
        return parts
    out: list[Chapter] = []
    current = Chapter(title, None, [])
    for idx, part in enumerate(parts):
        blocks = list(part.blocks)
        # Content warning lines repeat on every part; keep only the first.
        if idx > 0 and blocks and isinstance(blocks[0], Para) and _is_cw(blocks[0]):
            blocks.pop(0)
        pending_alias = part.url
        for b in blocks:
            if isinstance(b, Heading) and b.level == 1:
                if current.blocks or current.aliases or current.url:
                    out.append(current)
                current = Chapter(b.text, None, [])
                continue
            if pending_alias:
                current.aliases.append(pending_alias)
                pending_alias = None
            current.blocks.append(b)
        if pending_alias:
            current.aliases.append(pending_alias)
    out.append(current)
    out = [c for c in out if c.blocks]
    _title_intro(out[0] if out and out[0].title == title else None)
    return out


def _title_intro(intro: Chapter | None) -> None:
    """Name an untitled opening section after its own label line, e.g. "Foreword:"."""
    if intro is None:
        return
    for i, b in enumerate(intro.blocks):
        if not isinstance(b, Para) or _is_cw(b):
            continue
        label = plain_text(b.inlines).strip()
        if len(label) <= 30 and label.endswith(":"):
            intro.title = label.rstrip(":").strip()
            del intro.blocks[i]
        return


def _is_cw(p: Para) -> bool:
    return plain_text(p.inlines) == CONTENT_WARNING_TEXT


# --- commands -----------------------------------------------------------------


def cmd_list(site: Site, args) -> None:
    if not args.what:
        for v in site.volumes():
            n = len(v.chapters)
            extras = sum(c.is_extra for c in v.chapters)
            print(f"{v.key}: {v.title}, {n - extras} chapters" + (f" (+{extras} extras)" if extras else ""))
        print("archive: Volume 1 (Archive), the original 2016 version")
        for key, spec in BOOKS.items():
            print(f"{key}: {spec['title']} (book, use `twi book {key}`)")
        return
    what = args.what.lower()
    if what in BOOKS:
        spec = BOOKS[what]
        print(f"{spec['title']} starts at {spec['start']} (parts are found by following Next Chapter links)")
        return
    vol = site.volume(what)
    print(f"{vol.title}: {len(vol.chapters)} entries")
    for i, c in enumerate(vol.chapters, 1):
        print(f"{i}. {c.title}" + (" (extra, skipped by default)" if c.is_extra else ""))


def cmd_chapter(site: Site, args) -> None:
    refs = resolve_targets(site, args.targets)
    builder = Builder(site, Passwords(args.password, args.skip_locked), args)
    out_dir = Path(args.output)
    for i, ref in enumerate(refs, 1):
        log(f"[{i}/{len(refs)}] {ref.title}")
        ch = builder.chapter(ref)
        if ch is None:
            continue
        if args.format == "epub":
            path = out_dir / f"{safe_name(ch.title)}.epub"
            write_epub(path, ch.title, [ch])
        else:
            path = out_dir / f"{safe_name(ch.title)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(chapter_markdown(ch), "utf-8")
        log(f"wrote {path}")
    report_skipped(builder.pw)


def cmd_volume(site: Site, args) -> None:
    builder = Builder(site, Passwords(args.password, args.skip_locked), args)
    for key in args.volumes:
        vol = site.volume(key)
        refs = filter_extras(vol.chapters, args.include_extras)
        log(f"{vol.title}: {len(refs)} chapters")
        chapters = builder.many(refs)
        title = f"The Wandering Inn - {vol.title}"
        write_collection(title, chapters, args, Path(args.output))
    report_skipped(builder.pw)


def cmd_book(site: Site, args) -> None:
    builder = Builder(site, Passwords(args.password, args.skip_locked), args)
    for key in args.books:
        key = key.lower()
        if key not in BOOKS:
            raise SiteError(f"unknown book {key!r}; available: {', '.join(BOOKS)}")
        title, chapters = build_book(builder, site, key)
        args.single_file = True
        write_collection(title, chapters, args, Path(args.output))
    report_skipped(builder.pw)


def report_skipped(pw: Passwords) -> None:
    if pw.skipped:
        n = len(pw.skipped)
        log(f"skipped {n} locked chapter{'s' if n != 1 else ''}: " + "; ".join(pw.skipped))


# --- argument parsing ---------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", default=".", help="output directory (default: current directory)")
    common.add_argument("--password", action="append", default=[], metavar="PW",
                        help="password to try on locked chapters (repeatable; also TWI_PASSWORD)")
    common.add_argument("--skip-locked", action="store_true", help="skip locked chapters instead of asking")
    common.add_argument("--trigger-free", action="store_true",
                        help="use a chapter's trigger-free version when one exists (e.g. 9.68)")
    notes = common.add_mutually_exclusive_group()
    notes.add_argument("--keep-notes", dest="keep_notes", action="store_const", const=True,
                       help="keep author's notes and announcements (default for `chapter`)")
    notes.add_argument("--no-notes", dest="keep_notes", action="store_const", const=False,
                       help="remove author's notes and announcements (default for `volume` and `book`)")
    common.add_argument("--refresh", action="store_true", help="ignore cached pages and download again")
    common.add_argument("--single-file", action="store_true",
                        help="with --format md: write a volume as one file instead of a folder")
    common.add_argument("--include-extras", "--include-tales", action="store_true",
                        help="keep Tales of Innworld and other image-only/announcement posts")

    p = argparse.ArgumentParser(
        prog="twi",
        description="Download The Wandering Inn as clean Markdown or EPUB.",
        epilog="A chapter URL on its own works too: twi https://wanderinginn.com/...",
    )
    p.add_argument("--version", action="version", version=f"twi {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("list", help="list volumes, or the chapters of one volume")
    s.add_argument("what", nargs="?", help="volume number, 'archive', or a book name")

    s = sub.add_parser("chapter", parents=[common], help="download chapters (Markdown by default)")
    s.add_argument("targets", nargs="+", help="chapter title, URL, or 'latest'")
    s.add_argument("--format", choices=["md", "epub"], default="md")

    s = sub.add_parser("volume", parents=[common], help="download whole volumes (EPUB by default)")
    s.add_argument("volumes", nargs="+", help="volume number (1-10) or 'archive'")
    s.add_argument("--format", choices=["md", "epub"], default="epub")

    s = sub.add_parser("book", parents=[common], help="download a separate book, e.g. griefman")
    s.add_argument("books", nargs="+", help=f"one of: {', '.join(BOOKS)}")
    s.add_argument("--format", choices=["md", "epub"], default="epub")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and re.match(r"^(https?://|www\.|wanderinginn\.com)", argv[0], re.I):
        argv.insert(0, "chapter")
    args = build_parser().parse_args(argv)
    if getattr(args, "keep_notes", False) is None:
        # Single chapters keep the author's notes; volumes and books drop them.
        args.keep_notes = args.command == "chapter"
    site = Site(refresh=getattr(args, "refresh", False))
    try:
        {"list": cmd_list, "chapter": cmd_chapter, "volume": cmd_volume, "book": cmd_book}[args.command](site, args)
    except SiteBlocked as e:
        log(f"stopped: {e}")
        log("Chapters downloaded so far are cached, so running the same command later picks up quickly.")
        return 2
    except SiteError as e:
        log(f"error: {e}")
        return 1
    except KeyboardInterrupt:
        log("interrupted")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
