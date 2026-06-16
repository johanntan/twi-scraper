from pathlib import Path

from twi_scraper.paths import CACHE_DIR_ENV, default_cache_dir


def test_default_cache_dir_uses_xdg_cache_home(monkeypatch, tmp_path):
	monkeypatch.delenv(CACHE_DIR_ENV, raising=False)
	monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

	assert default_cache_dir() == tmp_path / "twi-scraper"


def test_default_cache_dir_falls_back_to_home_cache(monkeypatch, tmp_path):
	monkeypatch.delenv(CACHE_DIR_ENV, raising=False)
	monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
	monkeypatch.setattr(Path, "home", lambda: tmp_path)

	assert default_cache_dir() == tmp_path / ".cache" / "twi-scraper"


def test_default_cache_dir_allows_test_override(monkeypatch, tmp_path):
	monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path / "custom-cache"))

	assert default_cache_dir() == tmp_path / "custom-cache"
