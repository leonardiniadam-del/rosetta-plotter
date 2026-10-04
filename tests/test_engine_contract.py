"""Everything Rosetta Plotter uses from the EMS engine, checked in one place.

If this fails after an EMS update, compare the failing name with the new EMS source
before changing any Rosetta code.
"""
import inspect
import threading
from importlib.metadata import version

import pytest
from axidrawinternal import digest_svg, plot_warnings
from ink_extensions import simpletransform
from plotink import ebb_motion, ebb_serial, plot_utils
from pyaxidraw import axidraw


def test_engine_version_is_pinned():
    assert axidraw.AxiDraw().version_string == "3.9.6"
    assert version("axidrawinternal") == "3.9.6"


def test_engine_dependencies_match_ems_tested_versions():
    # Name checks can't catch version drift; constraints.txt pins these to EMS's tested set.
    assert version("plotink") == "1.9.0"
    assert version("ink_extensions") == "2.0.0"
    assert version("pyserial") == "3.5"


def test_internal_attributes_used_by_runner():
    ad = axidraw.AxiDraw()
    assert callable(ad.set_up_pause_receiver)
    assert hasattr(ad.plot_status, "stopped")
    assert hasattr(ad.plot_status.stats, "pt_estimate")
    assert hasattr(ad.plot_status.stats, "down_travel_inch")
    assert hasattr(ad.plot_status.stats, "down_travel_tot")
    assert hasattr(ad.pen.phys, "xpos")
    assert hasattr(ad.pen.phys, "ypos")


def test_helpers_used_by_plotter_and_flatten():
    for function in (
        ebb_motion.queryVoltage,
        ebb_motion.sendDisableMotors,
        ebb_serial.query_nickname,
        ebb_serial.write_nickname,
        ebb_serial.reboot,
        ebb_serial.min_version,
        ebb_serial.queryVersion,
        plot_utils.vb_scale,
        simpletransform.parseTransform,
        digest_svg.DigestSVG,
        plot_warnings.PlotWarnings,
    ):
        assert callable(function)


def _accepts(function, *args, **kwargs):
    inspect.signature(function).bind(*args, **kwargs)


def test_call_shapes_used_by_rosetta():
    port = object()
    _accepts(ebb_motion.queryVoltage, port, False)
    _accepts(ebb_motion.sendDisableMotors, port, False)
    _accepts(ebb_serial.query_nickname, port, False)
    _accepts(ebb_serial.write_nickname, port, "name")
    _accepts(ebb_serial.reboot, port)
    _accepts(ebb_serial.min_version, port, "2.5.5")
    _accepts(ebb_serial.queryVersion, port)
    _accepts(plot_utils.vb_scale, "0 0 1 1", None, 1.0, 1.0)
    _accepts(simpletransform.parseTransform, "scale(1,1)")
    _accepts(digest_svg.DigestSVG, default_logging=False)
    _accepts(
        digest_svg.DigestSVG(default_logging=False).process_svg,
        object(), plot_warnings.PlotWarnings(), [0] * 6, [[1, 0, 0], [0, 1, 0]],
    )
    _accepts(axidraw.AxiDraw().set_up_pause_receiver, threading.Event())


_LINE_100MM = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm" viewBox="0 0 200 100">'
    '<path d="M 0 50 L 100 50" stroke="black" fill="none"/></svg>'
)


def _preview_axidraw():
    ad = axidraw.AxiDraw()
    ad.plot_setup(_LINE_100MM)
    ad.options.mode = "plot"
    ad.options.preview = True
    ad.options.rendering = 0
    return ad


def test_preview_statistics_units():
    ad = _preview_axidraw()
    ad.plot_run()
    assert ad.plot_status.stopped == 0
    assert ad.plot_status.stats.down_travel_tot == pytest.approx(100 / 25.4)  # inches
    assert 1000 < ad.plot_status.stats.pt_estimate < 60000  # milliseconds


def test_pause_receiver_can_be_redirected():
    # plot_run() installs its own pause event through set_up_pause_receiver(); Rosetta's
    # runner redirects that call to its own event. If EMS changes this, pausing breaks.
    ad = _preview_axidraw()
    event = threading.Event()
    event.set()
    install_receiver = ad.set_up_pause_receiver
    ad.set_up_pause_receiver = lambda _ems_event: install_receiver(event)
    ad.plot_run()
    assert ad.plot_status.stopped == 103
