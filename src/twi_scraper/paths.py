"""Filesystem paths used by the CLI."""

from __future__ import annotations

import os
from pathlib import Path

CACHE_DIR_ENV = "TWI_SCRAPER_CACHE_DIR"


def default_cache_dir() -> Path:
	override = os.environ.get(CACHE_DIR_ENV)
	if override:
		return Path(override).expanduser()

	xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
	if xdg_cache_home:
		return Path(xdg_cache_home).expanduser() / "twi-scraper"

	return Path.home() / ".cache" / "twi-scraper"
