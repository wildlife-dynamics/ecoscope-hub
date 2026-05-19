#!/bin/bash
#
# Mirror the canonical infra (dev/ scripts + .github/workflows/ CI) from
# ../template/ into each workflow repo. The template tree mirrors the target
# layout 1:1, so this is a thin rsync wrapper.
#
# `pixi.toml` is a one-time bootstrap reference, not auto-synced: each repo
# owns its own name / published flag / compiler pin.
#
# Default target list lives in sync-targets.yaml (next to this script).
#
# Usage:
#   sync.sh                           # sync to all repos in sync-targets.yaml
#   sync.sh <repo_path> [repo_path]   # sync to specified repo(s) only
#   sync.sh --check                   # exit non-zero if any target is out of sync

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
template_dir="$script_dir/../template"
targets_file="$script_dir/sync-targets.yaml"

# Files in template/ that are per-repo customized and must NOT be overwritten
# by a sync. They live in template/ as a bootstrap reference only.
rsync_excludes=(--exclude='pixi.toml')

check_only=false
targets=()
for arg in "$@"; do
    case $arg in
        --check) check_only=true ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) targets+=("$arg") ;;
    esac
done

if [ ! -d "$template_dir" ]; then
    echo "ERROR: template dir not found at $template_dir" >&2
    exit 1
fi

if [ ${#targets[@]} -eq 0 ]; then
    if ! command -v yq >/dev/null 2>&1; then
        echo "ERROR: yq not found on PATH. Install go-yq or pass repo paths as args." >&2
        exit 1
    fi
    if [ ! -f "$targets_file" ]; then
        echo "ERROR: $targets_file not found." >&2
        exit 1
    fi
    while IFS= read -r path; do
        targets+=("${path/#\~/$HOME}")
    done < <(yq '.targets[]' "$targets_file" | tr -d '"\r')
fi

drift=0
for target in "${targets[@]}"; do
    if [ ! -d "$target" ]; then
        echo "skip: $target (not a directory)" >&2
        continue
    fi
    if [ "$check_only" = true ]; then
        # --checksum so mtime-only drift doesn't get flagged. -i emits a line
        # per file that would change; keep only file-transfer lines.
        out=$(rsync -ai --checksum --dry-run "${rsync_excludes[@]}" "$template_dir/" "$target/" | grep -E '^>f' || true)
        if [ -n "$out" ]; then
            echo "DRIFT in $target:"
            echo "$out" | sed 's/^/  /'
            drift=1
        fi
    else
        rsync -a "${rsync_excludes[@]}" "$template_dir/" "$target/"
        echo "synced: $target"
    fi
done

if [ "$check_only" = true ]; then
    if [ $drift -eq 0 ]; then
        echo "all targets in sync."
    fi
    exit $drift
fi
