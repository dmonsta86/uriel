#!/usr/bin/env sh
set -eu
ROOT="${1:-./example-question}"
uriel intake "Could plants retain a measurable response to earlier weather?" --root "$ROOT" || true
uriel audit --root "$ROOT" --profile exploratory || true
printf '\nOpen %s/.uriel/REMINDERS.md\n' "$ROOT"
