#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python -m auto_analyse --demo "$@"
.venv/bin/python -m auto_analyse.brand --demo "$@"
