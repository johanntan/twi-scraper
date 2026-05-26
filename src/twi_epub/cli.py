from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

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

app = typer.Typer(help="Download authorized Wandering Inn volumes for personal archives.")


@app.callback()
def root() -> None:
	"""Personal-use Wandering Inn archive tools."""


@app.command()
def download(
	volumes: Annotated[
		str,
		typer.Option(
			"--volumes",
			"-v",
			help="Volume numbers or ranges, for example '1', '1-3', or '1,3,5'.",
		),
	],
	formats: Annotated[
		str,
		typer.Option(
			"--formats",
			"-f",
			help="Comma-separated output formats: epub, md, or epub,md.",
		),
	] = "epub,md",
	output: Annotated[
		Path,
		typer.Option("--output", "-o", help="Output directory."),
	] = Path("out"),
	browser: Annotated[
		str | None,
		typer.Option(
			"--browser",
			help=f"Import Wandering Inn cookies from: {', '.join(SUPPORTED_BROWSERS)}.",
		),
	] = None,
	cookies_file: Annotated[
		Path | None,
		typer.Option(
			"--cookies-file",
			help="Netscape or JSON cookie export to use in addition to browser cookies.",
		),
	] = None,
	refresh: Annotated[
		bool,
		typer.Option("--refresh", help="Refetch chapters even when cached locally."),
	] = False,
) -> None:
	"""Download selected volumes and write one output file per volume."""

	try:
		volume_numbers = parse_volume_spec(volumes)
		output_formats = parse_format_spec(formats)
		output.mkdir(parents=True, exist_ok=True)

		with build_client(browser=browser, cookies_file=cookies_file) as client:
			selected = load_selected_volumes(client, volume_numbers)
			for volume in selected:
				typer.echo(f"Volume {volume.number}: {len(volume.chapters)} chapters")
				paths = download_volume(
					client,
					volume,
					output_dir=output,
					formats=output_formats,
					refresh=refresh,
				)
				for path in paths:
					typer.echo(f"Wrote {path}")
	except (TwiEpubError, ValueError, OSError) as exc:
		typer.echo(f"Error: {auth_hint(exc, browser)}", err=True)
		raise typer.Exit(code=1) from exc


if __name__ == "__main__":
	app()
