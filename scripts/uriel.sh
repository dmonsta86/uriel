#!/bin/sh
set -eu
REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -f "$REPO_DIR/dist/uriel.pyz" ]; then
  exec "${PYTHON:-python3}" "$REPO_DIR/dist/uriel.pyz" "$@"
fi
PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}" exec "${PYTHON:-python3}" -m uriel "$@"
