#!/usr/bin/env bash
# Setup script for Claude Code cloud sessions (claude.ai/code) and any Linux machine.
# Installs the Manzil package with pinned SUMO from PyPI; no GUI is needed (sumo runs headless).
set -euo pipefail
cd "$(dirname "$0")/.."
# A Debian-managed pip cannot uninstall itself, so a failed upgrade is not fatal.
python3 -m pip install --upgrade pip || echo "pip upgrade skipped; using the installed pip"
python3 -m pip install --progress-bar off -e ".[dev,kaggle]"
SUMO_HOME="$(python3 -c 'import sumo; print(sumo.SUMO_HOME)')"
LINE="export SUMO_HOME=\"$SUMO_HOME\""
grep -qxF "$LINE" "$HOME/.bashrc" 2>/dev/null || echo "$LINE" >> "$HOME/.bashrc"
python3 -m pytest -q tests/test_setup.py
