"""Start the Manzil API (and the built dashboard): ``python -m manzil.api [--port 8000]``."""

from __future__ import annotations

import argparse

import uvicorn

from manzil.api.app import DASHBOARD_DIST, create_app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    if not (DASHBOARD_DIST / "index.html").is_file():
        print("dashboard/dist not built: API only (build it with: cd dashboard; npm run build)")
    uvicorn.run(create_app(), host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
