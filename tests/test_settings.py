import json
import os

from rosetta.app.settings import (
    PaperChoice, PenProfile, Settings, SettingsStore, StoredIdentity, app_folder,
)
from rosetta.engine.options import Advanced


def _store_with(tmp_path, data) -> SettingsStore:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return SettingsStore(path)


def test_a_missing_file_gives_the_defaults(tmp_path):
    assert SettingsStore(tmp_path / "settings.json").settings == Settings()


def test_settings_survive_a_save_and_load(tmp_path):
    store = SettingsStore(tmp_path / "RosettaPlotter" / "settings.json")
    store.settings.units = "mm"
    store.settings.paper = PaperChoice("custom", "portrait", 300.0, 200.0)
    store.settings.margin_mm = 10.0
    store.settings.advanced = Advanced(accel=60, hiding=True)
    store.settings.profiles["PSU Lab m5p1"] = PenProfile(45, "marker")
    store.settings.old_firmware["COM7"] = StoredIdentity(3, 1, "Old one")
    store.save()
    assert SettingsStore(store.path).settings == store.settings


def test_a_damaged_file_is_set_aside(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    assert SettingsStore(path).settings == Settings()
    assert (tmp_path / "settings.json.bad").read_text(encoding="utf-8") == "{ not json"


def test_a_file_that_is_not_an_object_is_set_aside(tmp_path):
    assert _store_with(tmp_path, [1, 2]).settings == Settings()
    assert (tmp_path / "settings.json.bad").exists()


def test_one_bad_value_falls_back_to_its_default(tmp_path):
    settings = _store_with(tmp_path, {"units": "furlongs", "margin_mm": 12}).settings
    assert (settings.units, settings.margin_mm) == ("in", 12.0)


def test_bad_advanced_options_are_dropped_one_by_one(tmp_path):
    settings = _store_with(tmp_path, {"advanced": {"accel": 500, "speed_penup": 50, "warp": 1}}).settings
    assert settings.advanced == Advanced(speed_penup=50)


def test_a_custom_paper_without_its_size_falls_back(tmp_path):
    settings = _store_with(tmp_path, {"paper": {"size": "custom", "orientation": "portrait"}}).settings
    assert settings.paper == PaperChoice("letter", "portrait", None, None)


def test_profiles_keep_what_is_usable(tmp_path):
    settings = _store_with(tmp_path, {"profiles": {
        "PSU Lab m5p1": {"pen_down": 45, "pen_type": "marker"},
        "Other m1p1": {"pen_down": 99, "pen_type": "crayon"},
        "Broken": "not a profile",
    }}).settings
    assert settings.profiles == {"PSU Lab m5p1": PenProfile(45, "marker"), "Other m1p1": PenProfile()}


def test_old_firmware_identities_need_a_real_model(tmp_path):
    settings = _store_with(tmp_path, {"old_firmware": {
        "COM3": {"model": 5, "penlift": 3, "label": "Lab"},
        "COM4": {"model": 99},
        "COM5": {"model": 2, "penlift": "high"},
    }}).settings
    assert settings.old_firmware == {"COM3": StoredIdentity(5, 3, "Lab")}


def test_a_failed_save_is_logged_not_raised(tmp_path, monkeypatch, caplog):
    store = SettingsStore(tmp_path / "settings.json")

    def refuse(*args):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", refuse)
    store.save()
    assert "Couldn't save settings" in caplog.text


def test_app_folder_is_under_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert app_folder() == tmp_path / "RosettaPlotter"
