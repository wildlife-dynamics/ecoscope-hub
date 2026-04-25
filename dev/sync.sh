#!/bin/bash
#
# Copy the canonical dev scripts into each workflow repo's dev/ folder.
# The vendored copies are what CI invokes; this script keeps them in sync
# with the source of truth (this dir).
#
# Default target list lives in sync-targets.yaml (next to this script).
#
# Usage:
#   sync.sh                           # sync to all repos in sync-targets.yaml
#   sync.sh <repo_path> [repo_path]   # sync to specified repo(s) only
#   sync.sh --check                   # exit non-zero if any target is out of sync

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
targets_file="$script_dir/sync-targets.yaml"

# Files to sync into each target's dev/ folder.
FILES=(recompile.sh pytest-cli.sh setup-compile.sh setup-test.sh)

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
        # Expand leading ~ to $HOME (yaml does not do this).
        targets+=("${path/#\~/$HOME}")
    done < <(yq '.targets[]' "$targets_file" | tr -d '"\r')
fi

drift=0
for target in "${targets[@]}"; do
    if [ ! -d "$target" ]; then
        echo "skip: $target (not a directory)" >&2
        continue
    fi
    target_dev="$target/dev"
    mkdir -p "$target_dev"

    for f in "${FILES[@]}"; do
        src="$script_dir/$f"
        dst="$target_dev/$f"
        if [ "$check_only" = true ]; then
            if ! cmp -s "$src" "$dst"; then
                echo "DRIFT: $dst differs from $src"
                drift=1
            fi
        else
            cp "$src" "$dst"
            chmod +x "$dst"
            echo "synced: $dst"
        fi
    done
done

if [ "$check_only" = true ]; then
    if [ $drift -eq 0 ]; then
        echo "all targets in sync."
    fi
    exit $drift
fi
