#!/usr/bin/env bash
# The catalog owns command routes and both help displays.
set -euo pipefail
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
    printf 'Run this script instead of sourcing it.\n' >&2
    return 2
fi
tools_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
if (($# == 0)); then
    python3 -B "$tools_dir/command_catalog.py" help
    exit 2
fi
case $1 in
    -h|--help|help) exec python3 -B "$tools_dir/command_catalog.py" help ;;
esac
domain=
case $1 in
    code|documents|project) domain=$1; shift ;;
esac
if (($# == 0)); then
    python3 -B "$tools_dir/command_catalog.py" help >&2
    exit 2
fi
method=$1
shift
if [[ $method == doc-review && ( ${1:-} == -h || ${1:-} == --help ) ]]; then
    exec python3 -B "$tools_dir/command_catalog.py" method-help documents doc-review
fi
if ! route=$(python3 -B "$tools_dir/command_catalog.py" route "$domain" "$method" "${1:-}"); then
    printf 'Unknown domain or method: %s%s\n' "${domain:+$domain }" "$method" >&2
    exit 2
fi
IFS=$'\t' read -r kind target <<< "$route"
if [[ $kind == bash ]]; then
    exec bash "$tools_dir/$target" "$@"
fi
exec "${TOOLS_PYTHON:-python3}" -B "$tools_dir/$target" "$@"
