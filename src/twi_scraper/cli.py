from __future__ import annotations

import os
import sys
from pathlib import Path

import click
import httpx

from .auth import SUPPORTED_BROWSERS
from .downloader import (
	auth_hint,
	download_single_chapter,
	download_volume,
	load_selected_volumes,
	parse_volume_spec,
	resolve_chapter_selector,
)
from .errors import LockedChapterError, TwiScraperError
from .http import build_client
from .paths import default_cache_dir


@click.command(
	help="Download Wandering Inn volumes or individual chapters as Markdown or EPUB.",
	context_settings={"help_option_names": ["--help"]},
)
@click.argument("args", nargs=-1, metavar="[VOLUMES | chapter SELECTOR]")
@click.option(
	"--format",
	"-f",
	"output_format",
	type=click.Choice(("both", "epub", "md"), case_sensitive=False),
	default="both",
	show_default=True,
	help="Volume output format.",
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
	output_format: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
	refresh: bool,
) -> None:
	"""CLI entrypoint."""

	try:
		if args and args[0] == "chapter":
			selector = _resolve_chapter_argument(args)
			if output_format != "both":
				raise click.ClickException("--format only applies to volume downloads.")
			if refresh:
				raise click.ClickException("--refresh only applies to volume downloads.")
			_run_chapter(selector, output, browser, cookies_file)
		else:
			volumes = _resolve_volume_argument(args)
			_run_download(volumes, output_format, output, browser, cookies_file, refresh)
	except (TwiScraperError, httpx.HTTPError, TypeError, ValueError, OSError) as exc:
		raise click.ClickException(auth_hint(exc, browser)) from exc


def _resolve_chapter_argument(args: tuple[str, ...]) -> str:
	if len(args) != 2:
		raise click.ClickException(
			"Pass one chapter title, URL, or 'latest'. Example: twi chapter 1.05"
		)
	return args[1]


def _resolve_volume_argument(args: tuple[str, ...]) -> str:
	if len(args) > 1:
		raise click.ClickException("Pass one volume spec, for example '4' or '1-3'.")
	if args:
		return args[0]
	raise click.ClickException("Missing volume spec. Example: twi 4")


def _run_chapter(
	selector: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
) -> None:
	output.mkdir(parents=True, exist_ok=True)
	with build_client(browser=browser, cookies_file=cookies_file) as client:
		link = resolve_chapter_selector(client, selector)
		click.echo(f"Chapter: {link.title}")
		path = download_single_chapter(
			client, link, output_dir=output, password_provider=_password_for_chapter
		)
		click.echo(f"Wrote {path}")


def _run_download(
	volumes: str,
	output_format: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
	refresh: bool,
) -> None:
	volume_numbers = parse_volume_spec(volumes)
	output_formats = {"epub", "md"} if output_format == "both" else {output_format}
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
				password_provider=_password_for_chapter,
			)
			for path in paths:
				click.echo(f"Wrote {path}")


def _password_for_chapter(url: str) -> str:
	password = os.environ.get("TWI_PASSWORD")
	if password:
		return password
	if not sys.stdin.isatty():
		raise LockedChapterError(
			f"Chapter is locked: {url}. Set TWI_PASSWORD for noninteractive use."
		)
	return click.prompt("Chapter password", hide_input=True)


if __name__ == "__main__":
	app()
