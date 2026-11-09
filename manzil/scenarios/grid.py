"""Build the synthetic N×N signalised grid with ``netgenerate`` (PLAN task 1.1).

The grid is a test track for controllers, routing and the corridor. Every inner junction is a
traffic light; each border junction gets an extra "attached" fringe road so that all inner
junctions are four-arm intersections and traffic enters/leaves at dead-end fringe nodes.

Usage::

    python -m manzil.scenarios.grid            # writes scenarios/grid3x3/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from manzil.sumo_env import sumo_binary

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class GridSpec:
    """Parameters of the synthetic grid. Defaults are the FYP-1 3×3 test track."""

    size: int = 3  # junctions per side
    block_length_m: float = 200.0  # distance between neighbouring junctions
    fringe_length_m: float = 200.0  # length of the attached entry/exit roads
    lanes: int = 2  # lanes per direction
    speed_mps: float = 13.89  # 50 km/h urban limit
    tls_type: str = "static"  # SUMO's default fixed program; Manzil controllers replace it

    @property
    def name(self) -> str:
        return f"grid{self.size}x{self.size}"

    def junction_ids(self) -> list[str]:
        """netgenerate names grid junctions column letter + row number (A0, A1, ..., C2)."""
        if not 1 <= self.size <= 26:
            raise ValueError("grid size must be between 1 and 26")
        return [f"{chr(65 + x)}{y}" for x in range(self.size) for y in range(self.size)]


def netgenerate_command(spec: GridSpec, out_file: Path) -> list[str]:
    return [
        sumo_binary("netgenerate"),
        "--grid",
        "--grid.number", str(spec.size),
        "--grid.length", str(spec.block_length_m),
        "--grid.attach-length", str(spec.fringe_length_m),
        "--default.lanenumber", str(spec.lanes),
        "--default.speed", str(spec.speed_mps),
        "--default-junction-type", "priority",
        "--tls.set", ",".join(spec.junction_ids()),
        "--tls.default-type", spec.tls_type,
        "--no-turnarounds", "true",
        "--output-file", str(out_file),
    ]  # fmt: skip


def content_sha256(path: Path) -> str:
    """SHA-256 of a SUMO XML file without its leading "generated on <date>" comment.

    SUMO stamps every output with the generation time, so the raw file hash changes on each
    rebuild. Hashing from the end of that first comment gives a checksum that only changes when
    the network itself changes.
    """
    text = path.read_text(encoding="utf-8")
    start = text.find("<!-- generated on")
    if start != -1:
        text = text[text.index("-->", start) + 3 :]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sumo_version() -> str:
    out = subprocess.run(
        [sumo_binary("sumo"), "--version"], capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()[0].strip()


def build_grid(out_dir: Path, spec: GridSpec | None = None) -> Path:
    """Generate ``<name>.net.xml`` plus a ``network.json`` record (command, version, checksum)."""
    spec = spec or GridSpec()
    out_dir.mkdir(parents=True, exist_ok=True)
    net_file = out_dir / f"{spec.name}.net.xml"
    cmd = netgenerate_command(spec, net_file)
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    record = {
        "network": net_file.name,
        "synthetic": True,
        "generator": "netgenerate",
        "sumo_version": sumo_version(),
        "spec": asdict(spec),
        # Store the command with a relative output path so the record is machine-independent.
        "command": ["netgenerate", *cmd[1:-1], net_file.name],
        "content_sha256": content_sha256(net_file),
    }
    (out_dir / "network.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return net_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=3)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = GridSpec(size=args.size)
    out_dir = args.out_dir or REPO_ROOT / "scenarios" / spec.name
    net_file = build_grid(out_dir, spec)
    print(f"wrote {net_file}")


if __name__ == "__main__":
    main()
