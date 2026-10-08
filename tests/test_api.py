import json
from types import SimpleNamespace

import pytest

from rosetta.app.api import UNEXPECTED, Api
from rosetta.app.events import RecordingSink
from rosetta.app.settings import SettingsStore
from rosetta.engine.runner import PlotRunner
from tests.app_helpers import make_machine, wait_for
from tests.fake_ebb import FakeEBB, IFakeEBB, fake_factory, skip_engine_waits

DRAWING = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
<path d="M10 10 H90 V50 H10 Z" stroke="#000000" fill="none"/>
<path d="M20 30 H80" stroke="#ff0000" fill="none"/>
</svg>"""


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def make_api(tmp_path, ebb=None):
    machine, bench, store = make_machine(tmp_path, ebb)
    sink = RecordingSink()
    runner = PlotRunner(factory=fake_factory(FakeEBB(move_sleep=0)), poll_interval=0.001)
    return Api(store, sink, machine=machine, runner_factory=lambda: runner), sink


def ok(reply: dict) -> dict:
    assert reply["ok"], reply
    json.dumps(reply)  # everything has to cross the bridge as JSON
    return reply


def _drawing(tmp_path) -> str:
    path = tmp_path / "art.svg"
    path.write_text(DRAWING, encoding="utf-8")
    return str(path)


def _place(api, tmp_path, x=20.0, y=20.0) -> dict:
    """Import the test drawing into the Jobs list and place one copy; returns the piece."""
    job = ok(api.job_import(_drawing(tmp_path)))["job"]
    return ok(api.job_place(job["id"], x, y))["piece"]


def _plotter():
    return IFakeEBB(nickname="Lab m1p1", move_sleep=0)


def test_the_page_sees_only_bridge_methods(tmp_path):
    api, _sink = make_api(tmp_path)
    public = [name for name in dir(api) if not name.startswith("_")]
    assert public and all(callable(getattr(api, name)) for name in public)
    assert all(hasattr(getattr(Api, name), "__wrapped__") for name in public)  # each replies {"ok": ...}


def test_app_start_describes_everything(tmp_path):
    reply = ok(make_api(tmp_path)[0].app_start())
    assert reply["settings"]["units"] == "in"
    assert (len(reply["papers"]), len(reply["models"]), len(reply["pen_types"])) == (7, 7, 3)
    assert reply["machine"]["state"] == "no_plotter" and reply["plot"]["state"] == "idle"
    assert reply["material"]["width"] == pytest.approx(279.4)


def test_app_start_gives_the_advanced_defaults(tmp_path):
    defaults = ok(make_api(tmp_path)[0].app_start())["advanced_options"]["defaults"]
    assert defaults["accel"] == 75 and defaults["pen_up"] is None and defaults["hiding"] is False


def test_problems_come_back_in_plain_language(tmp_path):
    reply = make_api(tmp_path)[0].job_import(str(tmp_path / "drawing.afdesign"))
    assert not reply["ok"] and "In Affinity, use File › Export" in reply["message"]


def test_unexpected_errors_are_logged_and_explained(tmp_path, monkeypatch, caplog):
    api, _sink = make_api(tmp_path)
    monkeypatch.setattr(api._session, "load_job", lambda *args: 1 / 0)
    reply = api.job_import("x.svg")
    assert reply == {"ok": False, "message": UNEXPECTED, "details": "ZeroDivisionError: division by zero"}
    assert "job_import failed" in caplog.text


def test_settings_are_remembered(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_units("mm"))
    ok(api.material_set("a4", "portrait"))
    refused = api.set_advanced({"accel": 500})
    assert not refused["ok"] and refused["message"] == "Acceleration must be from 1 to 100."
    ok(api.set_advanced({"accel": 60}))
    saved = SettingsStore(tmp_path / "settings.json").settings
    assert (saved.units, saved.paper.size, saved.paper.orientation, saved.advanced.accel) == ("mm", "a4", "portrait", 60)


def test_advanced_changes_keep_the_other_options(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_advanced({"accel": 60}))
    advanced = ok(api.set_advanced({"hiding": True}))["advanced"]  # the page sends only what changed
    assert (advanced["accel"], advanced["hiding"]) == (60, True)
    assert SettingsStore(tmp_path / "settings.json").settings.advanced.accel == 60


def test_a_custom_paper_must_be_a_real_size(tmp_path):
    reply = make_api(tmp_path)[0].material_set("custom", "landscape", 0, 100)
    assert not reply["ok"] and "between 0 and 2000 mm" in reply["message"]


def test_jobs_place_arrange_and_list_pens(tmp_path):
    api, _sink = make_api(tmp_path)
    job = ok(api.job_import(_drawing(tmp_path)))["job"]
    assert job["id"] == "job-1" and job["groups"] and job["preview"].startswith("data:image/svg+xml")
    piece = ok(api.job_place(job["id"], 10, 20))["piece"]
    assert piece == {"id": "piece-1", "job_id": "job-1",
                     "placement": {"x": 10.0, "y": 20.0, "scale": 1.0, "scale_y": 1.0, "rotation": 0.0}}
    placed = ok(api.piece_place("piece-1", 10, 20, 0.5, 33.5, 0.25))["placement"]
    assert placed == {"x": 10.0, "y": 20.0, "scale": 0.5, "scale_y": 0.25, "rotation": 33.5}
    assert ok(api.piece_duplicate("piece-1"))["piece"]["id"] == "piece-2"
    ok(api.piece_delete("piece-1"))
    listed = ok(api.job_list())
    assert [j["id"] for j in listed["jobs"]] == ["job-1"] and [p["id"] for p in listed["pieces"]] == ["piece-2"]
    assert [color["name"] for color in ok(api.job_colors())["colors"]] == ["black", "red"]
    assert ok(api.artwork_pages(_drawing(tmp_path)))["pages"] == 1
    assert ok(api.job_remove("job-1"))["removed_pieces"] == ["piece-2"]
    assert ok(api.job_list()) == {"ok": True, "jobs": [], "pieces": []}


def test_a_whole_plot_through_the_bridge(tmp_path):
    api, sink = make_api(tmp_path, _plotter())
    assert ok(api.plotter_scan())["machine"]["state"] == "not_homed"
    assert ok(api.plotter_set_home())["machine"]["state"] == "ready"
    assert ok(api.plotter_jog(10, 5))["machine"]["position"] == pytest.approx([10, 5])
    ok(api.material_set("letter", "landscape"))
    _place(api, tmp_path)
    summary = ok(api.plot_prepare())["summary"]
    assert [layer["name"] for layer in summary["layers"]] == ["black", "red"]
    assert ok(api.plot_start())["plot"]["state"] == "load_pen"
    ok(api.plot_continue())
    wait_for(lambda: api.plot_status()["plot"]["state"] == "load_pen" and api.plot_status()["plot"]["layer"] == 1)
    ok(api.plot_continue())
    wait_for(lambda: api.plot_status()["plot"]["state"] == "done")
    assert sink.named("plot_progress")


def test_pen_settings_are_remembered_per_plotter(tmp_path):
    ebb = _plotter()
    api, _sink = make_api(tmp_path, ebb)
    ok(api.plotter_scan())
    ok(api.pen_set(45, "marker"))
    again, _sink = make_api(tmp_path, ebb)
    machine = ok(again.plotter_scan())["machine"]
    assert (machine["pen_down"], machine["pen_type"]) == (45, "marker")


def test_a_legal_advanced_pen_up_never_hides_the_plotter_later(tmp_path):
    """Advanced pen-up is kept per laptop, pen-down per plotter (loaded only once it's found): the next
    launch connects at the default pen-down, below this pen-up, and must still find the plotter."""
    ebb = _plotter()
    api, _sink = make_api(tmp_path, ebb)
    ok(api.plotter_scan())
    ok(api.pen_set(5, "fineliner"))
    ok(api.set_advanced({"pen_up": 20}))
    next_launch, _sink = make_api(tmp_path, ebb)
    machine = ok(next_launch.plotter_scan())["machine"]
    assert (machine["state"], machine["pen_down"]) == ("not_homed", 5)


def test_another_plotter_needs_the_plot_prepared_again(tmp_path):
    machine, bench, store = make_machine(tmp_path, _plotter())
    api = Api(store, RecordingSink(), machine=machine)
    ok(api.plotter_scan())
    ok(api.plotter_set_home())
    _place(api, tmp_path)
    ok(api.plot_prepare())
    bench.ebb.dead = True  # unplugged...
    bench.ebb = None
    assert ok(api.plotter_scan())["machine"]["state"] == "no_plotter"
    bench.ebb = _plotter()  # ...and plugged back in: the prepared plot still fits it
    ok(api.plotter_scan())
    assert ok(api.plot_status())["plot"]["state"] == "ready"
    bench.ebb.dead = True
    bench.ebb = IFakeEBB(nickname="Big m5p1", move_sleep=0)  # a bigger plotter instead
    assert ok(api.plotter_scan())["machine"]["model"] == 5
    assert ok(api.plot_status())["plot"]["state"] == "idle"
    ok(api.plot_prepare())
    ok(api.plotter_identify(2, 1, "Big"))  # renamed as another model
    assert ok(api.plot_status())["plot"]["state"] == "idle"


def test_mark_this_corner_uses_the_pen_position(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    assert not api.material_mark_corner()["ok"]  # not homed yet
    ok(api.plotter_set_home())
    ok(api.plotter_goto(25, 15))
    material = ok(api.material_mark_corner())["material"]
    assert (material["x"], material["y"]) == pytest.approx((25, 15))


def test_closing_when_nothing_is_plotting(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    assert api._on_closing() is True
    assert api.plotter_scan()["machine"]["state"] == "not_homed"  # shut down, then found again


def test_closing_mid_plot_asks_the_page_first(tmp_path):
    api, sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    ok(api.plotter_set_home())
    _place(api, tmp_path)
    ok(api.plot_prepare())
    ok(api.plot_start())  # waiting for the first pen
    assert api._on_closing() is False
    assert sink.named("close_requested") == [{}]
    destroyed = []
    api._attach_window(SimpleNamespace(destroy=lambda: destroyed.append(True)), choose_files=None)
    ok(api.quit_confirmed())
    assert destroyed and api._on_closing() is True


def test_quitting_mid_plot_pauses_it_before_the_window_closes(tmp_path, monkeypatch):
    machine, _bench, store = make_machine(tmp_path, _plotter())
    run_ebb = FakeEBB(move_sleep=0.01)
    runner = PlotRunner(factory=fake_factory(run_ebb), poll_interval=0.001)
    api = Api(store, RecordingSink(), machine=machine, runner_factory=lambda: runner)
    ok(api.plotter_scan())
    ok(api.plotter_set_home())
    _place(api, tmp_path)
    ok(api.plot_prepare())
    ok(api.plot_start())
    ok(api.plot_continue())
    wait_for(lambda: run_ebb.sm > 3)
    seen = []

    def destroy():
        seen.append((api.plot_status()["plot"]["state"], machine.state.value))

    api._attach_window(SimpleNamespace(destroy=destroy), choose_files=None)
    ok(api.quit_confirmed())  # a bridge thread: the slow part happens here, not on the window's thread
    assert seen == [("paused", "no_plotter")]
    monkeypatch.setattr(machine, "shutdown", lambda: pytest.fail("the closing event waited again"))
    assert api._on_closing() is True


def test_dropped_files_reach_the_page(tmp_path):
    api, sink = make_api(tmp_path)
    api._files_dropped(["C:\\art.svg"])
    assert sink.named("files_dropped") == [{"paths": ["C:\\art.svg"]}]


def test_the_file_picker(tmp_path):
    api, _sink = make_api(tmp_path)
    assert not api.artwork_choose()["ok"]
    api._attach_window(None, choose_files=lambda: ("C:\\a.svg", "C:\\b.pdf"))
    assert ok(api.artwork_choose())["paths"] == ["C:\\a.svg", "C:\\b.pdf"]


def test_an_old_pen_up_clash_does_not_block_other_advanced_options(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.pen_set(5, "fineliner"))
    ok(api.set_advanced({"pen_up": 20}))
    api._machine.pen_down = 30  # as another plotter's saved pen-down would (pen_set itself refuses a clash)
    assert ok(api.set_advanced({"accel": 60}))["advanced"]["accel"] == 60
    refused = api.set_advanced({"pen_up": 25})
    assert not refused["ok"] and "at least 10 above" in refused["message"]


def test_hidden_pens_are_left_out_of_the_plot(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    _place(api, tmp_path)
    ok(api.set_pen_visible("#ff0000", False))
    colors = ok(api.job_colors())["colors"]
    assert [(c["name"], c["visible"], c["layer"]) for c in colors] == [("black", True, 1), ("red", False, None)]
    assert [layer["name"] for layer in ok(api.plot_prepare())["summary"]["layers"]] == ["black"]


def test_rotate_paper_turns_the_layout_and_remembers_the_orientation(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.material_set("letter", "landscape"))
    _place(api, tmp_path, 10, 20)
    reply = ok(api.paper_rotate())
    assert (reply["material"]["width"], reply["material"]["height"]) == pytest.approx((215.9, 279.4))
    assert reply["paper"]["orientation"] == "portrait"
    assert reply["pieces"][0]["placement"]["rotation"] == 90.0
    assert SettingsStore(tmp_path / "settings.json").settings.paper.orientation == "portrait"


def test_rotating_custom_paper_flips_its_orientation(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.material_set("custom", "landscape", 500, 300))
    reply = ok(api.paper_rotate())
    assert reply["paper"] == {"size": "custom", "orientation": "portrait", "custom_width_mm": 300, "custom_height_mm": 500}


def test_centimetres_are_a_unit(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_units("cm"))
    assert SettingsStore(tmp_path / "settings.json").settings.units == "cm"
