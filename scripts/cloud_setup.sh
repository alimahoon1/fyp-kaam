#!/usr/bin/env bash
# Setup script for Claude Code cloud sessions (claude.ai/code) and any Linux machine.
# Installs the Manzil package with pinned SUMO from PyPI; no GUI is needed (sumo runs headless).
set -euo pipefail
cd "$(dirname "$0")/.."
# A Debian-managed pip cannot uninstall itself, so a failed upgrade is not fatal.
python3 -m pip install --upgrade pip || echo "pip upgrade skipped; using the installed pip"
python3 -m pip install --progress-bar off -e ".[dev]"
# Kaggle CLI (new-style API token via KAGGLE_API_TOKEN needs kaggle>=1.8, which needs Python>=3.11).
# Kept outside pyproject because the Windows venv uses Python 3.10. Optional: setup continues without it.
python3 -m pip install --progress-bar off "kaggle==2.2.5" six || echo "Kaggle CLI not installed (needs Python>=3.11)"
SUMO_HOME="$(python3 -c 'import sumo; print(sumo.SUMO_HOME)')"
LINE="export SUMO_HOME=\"$SUMO_HOME\""
grep -qxF "$LINE" "$HOME/.bashrc" 2>/dev/null || echo "$LINE" >> "$HOME/.bashrc"
python3 -m pytest -q tests/test_setup.py
