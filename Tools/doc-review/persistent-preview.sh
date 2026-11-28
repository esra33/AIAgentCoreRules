#!/usr/bin/env bash
# Run list or stop with a target from any directory. For project-based commands,
# use the project root or pass --project.
set -euo pipefail
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
    printf 'Run this script instead of sourcing it.\n' >&2
    return 2
fi
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${PREVIEW_PYTHON:-python3}" -B "$SCRIPT_DIR/doc_review.py" preview "$@"
