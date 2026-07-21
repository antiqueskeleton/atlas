"""
get_data_dir() frozen-mode behavior — the data-loss fix (2026-07-20).

Previously frozen mode returned sys._MEIPASS/data (the install dir), so
every Knowledge-page edit was destroyed by the next update's installer.
Frozen mode must now resolve to %APPDATA%\\Atlas\\data, seeded from the
bundle WITHOUT overwriting files the user already has. All tests are
APPDATA-isolated (tmp_path) per the verification-isolation rule.
"""
import sys

from backend.services import paths
from backend.services.paths import _seed_user_data, get_data_dir


def _freeze(monkeypatch, tmp_path, bundled_files: dict):
    """Simulate a PyInstaller runtime: sys.frozen + a fake _MEIPASS bundle."""
    bundle = tmp_path / "meipass" / "data"
    bundle.mkdir(parents=True)
    for name, content in bundled_files.items():
        (bundle / name).write_text(content, encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def test_source_mode_still_uses_project_data_dir():
    assert get_data_dir() == paths.Path(paths.__file__).resolve().parents[2] / "data"


def test_frozen_mode_resolves_to_appdata_not_install_dir(monkeypatch, tmp_path):
    _freeze(monkeypatch, tmp_path, {"brands.csv": "name\nFirman\n"})
    d = get_data_dir()
    assert d == tmp_path / "appdata" / "Atlas" / "data"
    assert str(tmp_path / "meipass") not in str(d)          # never the bundle
    # first call seeded the bundled file
    assert (d / "brands.csv").read_text(encoding="utf-8") == "name\nFirman\n"


def test_seeding_never_overwrites_user_edits(monkeypatch, tmp_path):
    """The whole point of the fix: an upgrade re-seeds, but a file the user
    edited must be left alone — their edits win over shipped defaults."""
    _freeze(monkeypatch, tmp_path, {"market_questions.csv": "SHIPPED DEFAULT"})
    d = get_data_dir()
    (d / "market_questions.csv").write_text("USER EDIT", encoding="utf-8")
    d2 = get_data_dir()                                     # simulate next launch
    assert (d2 / "market_questions.csv").read_text(encoding="utf-8") == "USER EDIT"


def test_upgrade_adds_new_bundled_files_alongside_kept_edits(monkeypatch, tmp_path):
    _freeze(monkeypatch, tmp_path, {"brands.csv": "v1"})
    d = get_data_dir()
    (d / "brands.csv").write_text("edited", encoding="utf-8")
    # the next release ships an additional CSV
    (tmp_path / "meipass" / "data" / "channels.csv").write_text("new-in-v2",
                                                                encoding="utf-8")
    d2 = get_data_dir()
    assert (d2 / "brands.csv").read_text(encoding="utf-8") == "edited"
    assert (d2 / "channels.csv").read_text(encoding="utf-8") == "new-in-v2"


def test_seed_survives_missing_bundle_dir(tmp_path):
    """A broken/missing bundle must not raise — the app degrades to whatever
    files exist, same as any missing CSV."""
    _seed_user_data(tmp_path / "user", tmp_path / "nonexistent")
    assert (tmp_path / "user").is_dir()
