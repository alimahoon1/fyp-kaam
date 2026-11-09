"""Locate the SUMO installation (pip ``eclipse-sumo`` package or a system install)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def sumo_home() -> Path:
    """Return SUMO_HOME: the env variable if it is a full SUMO install, else the pip package.

    Importing ``libsumo`` sets ``SUMO_HOME`` to the ``sumo_data`` package, which has no tools or
    binaries, so the variable is only trusted when it contains SUMO's ``tools`` folder.
    """
    env = os.environ.get("SUMO_HOME")
    if env and (Path(env) / "tools").is_dir():
        return Path(env)
    import sumo  # provided by the eclipse-sumo package

    return Path(sumo.SUMO_HOME)


def sumo_binary(name: str = "sumo") -> str:
    """Return the full path of a SUMO executable (``sumo``, ``sumo-gui``, ``netgenerate``)."""
    found = shutil.which(name)
    if found:
        return found
    bin_dir = sumo_home() / "bin"
    for candidate in (bin_dir / name, bin_dir / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"SUMO executable {name!r} not found; run: pip install -e .[dev]")


def sumo_tool(relative: str) -> Path:
    """Return the path of a script in SUMO's tools folder, e.g. ``randomTrips.py``."""
    path = sumo_home() / "tools" / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
