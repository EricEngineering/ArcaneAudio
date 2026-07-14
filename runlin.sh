#!/usr/bin/env bash
set -e

# Always run from the folder containing this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Launching ArcaneAudio..."

# Activate virtualenv if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 -m arcaneaudio
status=$?

if [ $status -ne 0 ]; then
    echo
    echo "[ERROR] ArcaneAudio exited with code $status"
fi