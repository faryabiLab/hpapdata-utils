#!/usr/bin/env bash
# Double-click-friendly launcher for generate_id.py
# Creates a local virtual environment on first run (so it doesn't touch
# your system Python), then runs the 2nd ID generator.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "First run: setting up (this happens once)..."
    python3 -m venv .venv
    ".venv/bin/pip" install --quiet -r requirements.txt
fi

".venv/bin/python3" generate_id.py
