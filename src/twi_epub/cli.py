from __future__ import annotations

from pathlib import Path

import click

from .auth import SUPPORTED_BROWSERS
from .downloader import (
	auth_hint,
	download_volume,
	load_selected_volumes,
	parse_format_spec,
	parse_volume_spec,
)
from .errors import TwiEpubError
from .http import build_client


@click.command(
	help="Download authorized Wandering Inn volumes for personal archives.",
	context_settings={"help_option_names": ["--help"]},
)
@click.argument("args", nargs=-1, metavar="[VOLUMES]")
@click.option(
	"--volumes",
	"-v",
	"volumes_option",
	help="Backward-compatible volume numbers or ranges option.",
)
@click.option(
	"--formats",
	"-f",
	default="epub,md",
	show_default=True,
	help="Comma-separated output formats: epub, md, or epub,md.",
)
@click.option(
	"--output",
	"-o",
	type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
	default=Path("out"),
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
	volumes_option: str | None,
	formats: str,
	output: Path,
	browser: str | None,
	cookies_file: Path | None,
	refresh: bool,
) -> None:
	"""CLI entrypoint."""

	volumes = _resolve_volume_argument(args, volumes_option)
	_run_download(
		volumes=volumes,
		formats=formats,
		output=output,
		browser=browser,
		cookies_file=cookies_file,
		refresh=refresh,
	)


def _resolve_volume_argument(args: tuple[str, ...], volumes_option: str | None) -> str:
	args = tuple(args)
	if args and args[0] == "download":
		args = args[1:]

	if len(args) > 1:
		raise click.ClickException("Pass one volume spec, for example '4' or '1-3'.")
	if args and volumes_option:
		raise click.ClickException("Pass volumes either positionally or with --volumes, not both.")
	if args:
		return args[0]
	if volumes_option:
		return volumes_option
	raise click.ClickException("Missing volume spec. Example: twi-epub 4")


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

		with build_client(browser=browser, cookies_file=cookies_file) as client:
			selected = load_selected_volumes(client, volume_numbers)
			for volume in selected:
				click.echo(f"Volume {volume.number}: {len(volume.chapters)} chapters")
				paths = download_volume(
					client,
					volume,
					output_dir=output,
					formats=output_formats,
					refresh=refresh,
				)
				for path in paths:
					click.echo(f"Wrote {path}")
	except (TwiEpubError, ValueError, OSError) as exc:
		raise click.ClickException(auth_hint(exc, browser)) from exc


if __name__ == "__main__":
	app()
