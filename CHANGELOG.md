# Changelog

All notable changes to `twi-scraper`. The newest version is first.

Each version's section becomes its GitHub release notes, so write entries for readers:
what changed for them, not how the code changed.

## [Unreleased]

### Fixed

- Bold bracketed lines at the start of a chapter are no longer mistaken for announcements.
  Interlude – The Call (the first chapter of Volume 2) kept losing its opening lines.

## [0.1.1] - 2026-11-12

### Fixed

- `twi chapter` (which keeps author's notes) now also removes opening announcements, such as
  7.25's "(Volume 2 … is now available for preorder on Audible!)". An author's note at the top
  of a chapter is still kept.

## [0.1.0] - 2026-11-10

First release.

### Added

- `twi chapter`: download chapters as Markdown by title, by URL, or `latest`. The author's notes
  are kept under an "Author's Note" heading.
- `twi volume`: download whole volumes as EPUB, including the original 2016 Volume 1 archive.
  Author's notes and announcements are removed.
- `twi book griefman`: Griefman as one file, split by the book's own chapters.
- Locked chapters: asks for the password, and remembers which password works for each
  Patreon tier so a wrong password is never sent twice.
- `--trigger-free`: downloads 9.68's trigger-free version instead, using the password printed
  in the chapter.
- Links between chapters (Solstice) stay inside the EPUB.
- Screen-reader fixes: redacted text reads as "[redacted]" with the hidden words in a footnote,
  and "fancy font" letters (small caps, superscripts, upside-down text) become plain letters.
- Gallery images, fan-art credits, navigation links and Tales of Innworld are left out.
