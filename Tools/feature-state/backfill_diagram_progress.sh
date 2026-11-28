#!/usr/bin/env bash
# Compatibility path for link-diagram-tasks.sh.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/../link-diagram-tasks/link-diagram-tasks.sh" "$@"
