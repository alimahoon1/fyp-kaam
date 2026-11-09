#!/usr/bin/env bash
# Setup script for Claude Code cloud sessions (claude.ai/code) and any Linux machine.
# Installs the Manzil package with pinned SUMO from PyPI; no GUI is needed (sumo runs headless).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]"
SUMO_HOME="$(python3 -c 'import sumo; print(sumo.SUMO_HOME)')"
echo "export SUMO_HOME=\"$SUMO_HOME\"" >> "$HOME/.bashrc"
python3 -m pytest -q tests/test_setup.py
