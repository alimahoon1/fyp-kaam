"""Experiment store command line (W5).

::

    python -m manzil.store import                      # results/, runs/live/, tracking results
    python -m manzil.store import --root results/phase2
    python -m manzil.store summary
    python -m manzil.store list --study results/phase2/comparison --controller adaptive
    python -m manzil.store export --study results/phase2/comparison --out export.json   # FR-19
    python -m manzil.store export --run <run_key> --run <run_key> --out export.csv

The default database is ``runs/manzil.sqlite`` (git-ignored; it can be rebuilt at any time
from the run folders with ``import``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from manzil.experiments.runner import REPO_ROOT
from manzil.store.export import write_export
from manzil.store.importer import import_all, import_runs
from manzil.store.repository import SqliteRepository

DEFAULT_DB = REPO_ROOT / "runs" / "manzil.sqlite"


def _filters(a) -> dict:
    keys = ("study", "source", "controller", "profile", "status", "label", "arm")
    return {k: getattr(a, k) for k in keys if getattr(a, k, None)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m manzil.store", description=__doc__.split("\n")[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("import", help="import run folders and perception results")
    pi.add_argument("--root", type=Path, action="append", help="only this folder (repeatable)")
    sub.add_parser("summary", help="counts per table and per study")
    for name in ("list", "export"):
        sp = sub.add_parser(name)
        for f in ("study", "source", "controller", "profile", "status", "label", "arm"):
            sp.add_argument(f"--{f}")
        if name == "export":
            sp.add_argument("--run", action="append", default=[], help="run key (repeatable)")
            sp.add_argument("--out", type=Path, required=True, help=".json or .csv")
    a = p.parse_args(argv)
    repo = SqliteRepository(a.db)
    if a.cmd == "import":
        if a.root:
            rep = [import_runs(repo, r.resolve(), REPO_ROOT) for r in a.root]
        else:
            rep = import_all(repo, REPO_ROOT)
        print(json.dumps(rep, indent=2))
    elif a.cmd == "summary":
        print(json.dumps(repo.summary(), indent=2))
    elif a.cmd == "list":
        for r in repo.list_runs(**_filters(a)):
            print(f"{r['status']:9} {r['controller'] or '-':10} {r['profile'] or '-':7} "
                  f"s{r['seed']}  {r['run_key']}")  # fmt: skip
    elif a.cmd == "export":
        keys = a.run or [r["run_key"] for r in repo.list_runs(**_filters(a))]
        if not keys:
            print("no runs match", file=sys.stderr)
            return 1
        out = write_export(repo, keys, a.out)
        print(f"exported {len(keys)} runs to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
