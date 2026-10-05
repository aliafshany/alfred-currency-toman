#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/dist"
out="$root/dist/Currency Toman.alfredworkflow"
rm -f "$out"
(
  cd "$root/workflow"
  zip -X -r "$out" info.plist currency.py render_flags.swift icon.png
)
echo "$out"
