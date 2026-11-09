"""Phase 0 checks: the package imports and SUMO is installed and runnable."""

import subprocess

import manzil
from manzil.sumo_env import sumo_binary, sumo_home, sumo_tool


def test_package_imports():
    assert manzil.__version__


def test_sumo_home_exists():
    assert sumo_home().is_dir()


def test_sumo_binaries_run():
    for name in ("sumo", "netgenerate"):
        out = subprocess.run([sumo_binary(name), "--version"], capture_output=True, text=True)
        assert out.returncode == 0
        assert "Eclipse SUMO" in out.stdout


def test_random_trips_tool_present():
    assert sumo_tool("randomTrips.py").is_file()


def test_sumo_home_survives_libsumo_import():
    """libsumo sets SUMO_HOME to the data-only package; tools must still be found."""
    import libsumo  # noqa: F401

    assert sumo_tool("randomTrips.py").is_file()
