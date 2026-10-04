"""Everything Rosetta Plotter uses from the EMS engine, checked in one place.

If this fails after an EMS update, compare the failing name with the new EMS source
before changing any Rosetta code.
"""
from importlib.metadata import version

from axidrawinternal import digest_svg, plot_warnings
from ink_extensions import simpletransform
from plotink import ebb_motion, ebb_serial, plot_utils
from pyaxidraw import axidraw


def test_engine_version_is_pinned():
    assert axidraw.AxiDraw().version_string == "3.9.6"


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
