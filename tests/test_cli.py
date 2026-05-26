from pathlib import Path

from click.testing import CliRunner

from twi_epub import cli
from twi_epub.models import Volume


class DummyClient:
	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, tb):
		return False


def test_root_command_accepts_positional_volume(monkeypatch, tmp_path):
	calls = []

	def fake_load_selected_volumes(client, volume_numbers):
		calls.append(("load", volume_numbers))
		return [Volume(number=4, title="Volume 4")]

	def fake_download_volume(client, volume, *, output_dir, formats, refresh):
		calls.append(("download", volume.number, output_dir, formats, refresh))
		return [output_dir / "volume-04.md"]

	monkeypatch.setattr(cli, "build_client", lambda **kwargs: DummyClient())
	monkeypatch.setattr(cli, "load_selected_volumes", fake_load_selected_volumes)
	monkeypatch.setattr(cli, "download_volume", fake_download_volume)

	result = CliRunner().invoke(
		cli.app,
		["4", "--formats", "md", "--output", str(tmp_path)],
	)

	assert result.exit_code == 0, result.output
	assert ("load", [4]) in calls
	assert ("download", 4, Path(tmp_path), {"md"}, False) in calls
	assert "Wrote" in result.output


def test_download_alias_still_accepts_volumes_option(monkeypatch, tmp_path):
	calls = []

	def fake_load_selected_volumes(client, volume_numbers):
		calls.append(("load", volume_numbers))
		return [Volume(number=4, title="Volume 4")]

	def fake_download_volume(client, volume, *, output_dir, formats, refresh):
		calls.append(("download", volume.number, output_dir, formats, refresh))
		return [output_dir / "volume-04.md"]

	monkeypatch.setattr(cli, "build_client", lambda **kwargs: DummyClient())
	monkeypatch.setattr(cli, "load_selected_volumes", fake_load_selected_volumes)
	monkeypatch.setattr(cli, "download_volume", fake_download_volume)

	result = CliRunner().invoke(
		cli.app,
		["download", "--volumes", "4", "--formats", "md", "--output", str(tmp_path)],
	)

	assert result.exit_code == 0, result.output
	assert ("load", [4]) in calls
	assert ("download", 4, Path(tmp_path), {"md"}, False) in calls
