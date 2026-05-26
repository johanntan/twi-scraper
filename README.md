# twi-epub

Personal-use downloader for building local Markdown and EPUB archives from the
official Wandering Inn table of contents.

This tool does not bypass Patreon, password, or login gates. For locked chapters
it can reuse cookies from a browser where you are already authorized.

## Install

```bash
uv sync
```

## Usage

Download selected volumes to both EPUB and Markdown:

```bash
uv run twi-epub 3 --formats epub,md --output out/
```

Use authorized cookies from a logged-in browser for protected chapters:

```bash
uv run twi-epub 1-2 --browser chrome --output out/
```

If direct browser cookie access fails, export cookies for `wanderinginn.com` in
Netscape or JSON format and pass:

```bash
uv run twi-epub 1-2 --cookies-file cookies.txt --output out/
```

Refresh cached chapters:

```bash
uv run twi-epub 3 --refresh --output out/
```

Outputs are written as `volume-NN.md`, `volume-NN.epub`, and cache/manifest data
under `out/.cache/`.

The older subcommand form still works for existing shell history or scripts:

```bash
uv run twi-epub download --volumes 3
```
