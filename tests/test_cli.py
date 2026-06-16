from pathlib import Path

from click.testing import CliRunner

from twi_scraper import cli
from twi_scraper.models import ChapterLink, Volume


class DummyClient:
	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, tb):
		return False


def test_root_command_accepts_positional_volume(monkeypatch, tmp_path):
	calls = []
	cache_dir = tmp_path / "cache"

	def fake_load_selected_volumes(client, volume_numbers):
		calls.append(("load", volume_numbers))
		return [Volume(number=4, title="Volume 4")]

	def fake_download_volume(client, volume, *, output_dir, cache_dir, formats, refresh):
		calls.append(("download", volume.number, output_dir, cache_dir, formats, refresh))
		return [output_dir / "volume-04.md"]

	monkeypatch.setattr(cli, "build_client", lambda **kwargs: DummyClient())
	monkeypatch.setattr(cli, "load_selected_volumes", fake_load_selected_volumes)
	monkeypatch.setattr(cli, "download_volume", fake_download_volume)
	monkeypatch.setattr(cli, "default_cache_dir", lambda: cache_dir)

	result = CliRunner().invoke(
		cli.app,
		["4", "--formats", "md", "--output", str(tmp_path)],
	)

	assert result.exit_code == 0, result.output
	assert ("load", [4]) in calls
	assert ("download", 4, Path(tmp_path), cache_dir, {"md"}, False) in calls
	assert "Wrote" in result.output


def test_root_command_defaults_output_to_current_directory(monkeypatch, tmp_path):
	calls = []

	def fake_load_selected_volumes(client, volume_numbers):
		return [Volume(number=4, title="Volume 4")]

	def fake_download_volume(client, volume, *, output_dir, cache_dir, formats, refresh):
		calls.append((output_dir, cache_dir))
		return [output_dir / "volume-04.md"]

	monkeypatch.setattr(cli, "build_client", lambda **kwargs: DummyClient())
	monkeypatch.setattr(cli, "load_selected_volumes", fake_load_selected_volumes)
	monkeypatch.setattr(cli, "download_volume", fake_download_volume)
	monkeypatch.setattr(cli, "default_cache_dir", lambda: tmp_path / "cache")

	with CliRunner().isolated_filesystem(temp_dir=tmp_path):
		result = CliRunner().invoke(cli.app, ["4", "--formats", "md"])

	assert result.exit_code == 0, result.output
	assert calls == [(Path("."), tmp_path / "cache")]


def test_removed_download_alias_is_rejected():
	result = CliRunner().invoke(cli.app, ["download", "--volumes", "4"])

	assert result.exit_code != 0


def test_chapter_command_resolves_selector_and_forwards_browser_cookies(monkeypatch, tmp_path):
	calls = []
	link = ChapterLink(
		title="1.05",
		url="https://wanderinginn.com/2017/03/03/rw1-05/",
	)

	def fake_build_client(**kwargs):
		calls.append(("client", kwargs))
		return DummyClient()

	def fake_resolve_chapter_selector(client, selector):
		calls.append(("resolve", selector))
		return link

	def fake_download_single_chapter(client, selected, *, output_dir):
		calls.append(("download", selected, output_dir))
		return output_dir / "TWI-1.05.md"

	monkeypatch.setattr(cli, "build_client", fake_build_client)
	monkeypatch.setattr(cli, "resolve_chapter_selector", fake_resolve_chapter_selector)
	monkeypatch.setattr(cli, "download_single_chapter", fake_download_single_chapter)

	result = CliRunner().invoke(
		cli.app,
		["chapter", "1.05", "--browser", "firefox", "--output", str(tmp_path)],
	)

	assert result.exit_code == 0, result.output
	assert ("client", {"browser": "firefox", "cookies_file": None}) in calls
	assert ("resolve", "1.05") in calls
	assert ("download", link, Path(tmp_path)) in calls
	assert "Wrote" in result.output
