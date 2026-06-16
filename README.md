# twi-scraper

> This project was created with substantial AI assistance.

`twi-scraper` downloads chapters from [The Wandering Inn](https://wanderinginn.com/) and builds personal Markdown or EPUB archives. It can download a complete volume, a range of volumes, one named chapter, or the latest chapter.

This project is not affiliated with pirateaba or The Wandering Inn. The MIT license covers this program's source code only. The story, website, and downloaded chapter content remain the property of their respective copyright holders. Keep generated files for personal use and do not redistribute them.

## Install

Install the command directly from GitHub with `uv`:

```bash
uv tool install git+https://github.com/johanntan/twi-scraper.git
```

Update or remove it later with:

```bash
uv tool install update twi-scraper
uv tool uninstall twi-scraper
```

Python 3.11 or newer is supported. uv can install a suitable Python interpreter automatically when needed.

## Download volumes

Download Volume 10 as both EPUB and Markdown:

```bash
twi-scraper 10
```

Volume ranges and comma-separated selections work too:

```bash
twi-scraper 1-3
twi-scraper 3,5,7-9
```

Choose the output format or directory:

```bash
twi-scraper 10 --formats epub
twi-scraper 10 --formats md --output ~/Books/WanderingInn
```

Volume output is written as `volume-NN.epub` and `volume-NN.md` in the current directory by default. Use `--output` when you want generated files somewhere else.

Downloaded chapter data and manifests are cached outside the output directory:

- `$XDG_CACHE_HOME/twi-scraper` when `XDG_CACHE_HOME` is set.
- `~/.cache/twi-scraper` otherwise.

Use `--refresh` to refetch chapters even when they are already cached.

## Download one chapter

Download a chapter as Markdown using its table-of-contents title:

```bash
twi-scraper chapter 1.05
```

The selector can also be `latest` or a direct chapter URL:

```bash
twi-scraper chapter latest
twi-scraper chapter https://wanderinginn.com/2020/01/26/7-02/
```

Single-chapter files are named like `TWI-1.05.md`. They keep author notes and promotional text while still removing site navigation and normalizing the text.

## Authorized chapters

`twi-scraper` does not bypass passwords, subscriptions, or login gates. It can reuse cookies from a browser where you already have access:

```bash
twi-scraper 1-2 --browser firefox
twi-scraper chapter latest --browser firefox
```

Supported browsers are Firefox, Chrome, Edge, and Safari. Browser cookie access depends on the operating system and browser security settings; Firefox is generally the most reliable option.

You can instead provide an authorized Netscape or JSON cookie export:

```bash
twi-scraper 1-2 --cookies-file cookies.txt
```

## Output cleanup

The generated files apply cleanup intended for comfortable reading:

- Chapter titles link back to their source pages.
- Previous/next chapter navigation and site widgets are removed.
- Dash-only scene breaks become Markdown-compatible `***` separators.
- Stylized Unicode letters are normalized.
- Recoverable CSS-hidden text is exposed and labeled `Redacted in original`.
- Literal block redactions are represented as `[redacted]`.
- Volume builds remove detected author-note tails and known promotional notices.
- Known catalog corrections are applied to Volumes 1 and 2.
- Image-only `Tales of Innworld` comic entries are excluded from Volume 10 builds, but can still be downloaded individually.

The downloader waits at least one second between network requests and retries temporary server failures with bounded backoff.

## Development

Clone the repository, then install the project and development tools:

```bash
git clone https://github.com/johanntan/twi-scraper.git
cd twi-scraper
uv sync --dev
```

Run the local command and checks:

```bash
uv run twi-scraper 10
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Changes

### 0.1.0

Initial release.

## License

The program source code is available under the [MIT License](LICENSE). The license does not grant rights to The Wandering Inn text, artwork, website content, or other third-party material.
