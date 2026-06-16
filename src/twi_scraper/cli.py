from __future__ import annotations

from pathlib import Path

import click

from .auth import SUPPORTED_BROWSERS
from .downloader import (
	auth_hint,
	download_single_chapter,
	download_volume,
	load_selected_volumes,
	parse_format_spec,
	parse_volume_spec,
	resolve_chapter_selector,
)
from .errors import TwiScraperError
from .http import build_client
from .paths import default_cache_dir


@click.command(
	help="Download Wandering Inn volumes or individual chapters as Markdown or EPUB.",
	context_settings={"help_option_names": ["--help"]},
)
@click.argument("args", nargs=-1, metavar="[VOLUMES | chapter SELECTOR]")
@click.option(
	"--formats",
	"-f",
	default="epub,md",
	show_default=True,
	help="Volume output formats: epub, md, or epub,md.",
)
@click.option(
	"--output",
	"-o",
	type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
	default=Path("."),
	show_default=True,
	help="Output directory.",
)
@click.option(
	"--browser",
	type=click.Choice(SUPPORTED_BROWSERS, case_sensitive=False),
	help="Import Wandering Inn cookies from this browser.",
)
@click.option(
	"--cookies-file",
	type=click.Path(path_type=Path, exists=True, dir_okay=False),
	help="Netscape or JSON cookie export to use in addition to browser cookies.",
)
@click.option(
	"--refresh",
	is_flag=True,
	help="Refetch chapters even when cached locally.",
)
def app(
	args: tuple[str, ...],
	formats: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
	refresh: bool,
) -> None:
	"""CLI entrypoint."""

	if args and args[0] == "chapter":
		selector = _resolve_chapter_argument(args)
		if formats != "epub,md":
			raise click.ClickException("--formats only applies to volume downloads.")
		if refresh:
			raise click.ClickException("--refresh only applies to volume downloads.")
		_run_chapter(
			selector=selector,
			output=output,
			browser=browser,
			cookies_file=cookies_file,
		)
		return

	volumes = _resolve_volume_argument(args)
	_run_download(
		volumes=volumes,
		formats=formats,
		output=output,
		browser=browser,
		cookies_file=cookies_file,
		refresh=refresh,
	)


def _resolve_chapter_argument(args: tuple[str, ...]) -> str:
	if len(args) != 2:
		raise click.ClickException(
			"Pass one chapter title, URL, or 'latest'. Example: twi-scraper chapter 1.05"
		)
	return args[1]


def _resolve_volume_argument(args: tuple[str, ...]) -> str:
	if len(args) > 1:
		raise click.ClickException("Pass one volume spec, for example '4' or '1-3'.")
	if args:
		return args[0]
	raise click.ClickException("Missing volume spec. Example: twi-scraper 4")


def _run_chapter(
	*,
	selector: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
) -> None:
	try:
		output.mkdir(parents=True, exist_ok=True)
		with build_client(browser=browser, cookies_file=cookies_file) as client:
			link = resolve_chapter_selector(client, selector)
			click.echo(f"Chapter: {link.title}")
			path = download_single_chapter(client, link, output_dir=output)
			click.echo(f"Wrote {path}")
	except (TwiScraperError, ValueError, OSError) as exc:
		raise click.ClickException(auth_hint(exc, browser)) from exc


def _run_download(
	*,
	volumes: str,
	formats: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
	refresh: bool,
) -> None:
	try:
		volume_numbers = parse_volume_spec(volumes)
		output_formats = parse_format_spec(formats)
		output.mkdir(parents=True, exist_ok=True)
		cache_dir = default_cache_dir()

		with build_client(browser=browser, cookies_file=cookies_file) as client:
			selected = load_selected_volumes(client, volume_numbers)
			for volume in selected:
				click.echo(f"Volume {volume.number}: {len(volume.chapters)} chapters")
				paths = download_volume(
					client,
					volume,
					output_dir=output,
					cache_dir=cache_dir,
					formats=output_formats,
					refresh=refresh,
				)
				for path in paths:
					click.echo(f"Wrote {path}")
	except (TwiScraperError, ValueError, OSError) as exc:
		raise click.ClickException(auth_hint(exc, browser)) from exc


if __name__ == "__main__":
	app()
