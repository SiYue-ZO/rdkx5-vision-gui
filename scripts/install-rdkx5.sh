#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y python3-pyqt5 python3-opencv python3-venv libxcb-xinerama0
uv sync --no-extra
echo "RDK system packages and project environment are ready. Run: uv run python main.py"

