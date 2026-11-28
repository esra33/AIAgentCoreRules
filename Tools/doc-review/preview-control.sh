#!/usr/bin/env bash
# Compatibility path for persistent-preview.sh.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/persistent-preview.sh" "$@"
