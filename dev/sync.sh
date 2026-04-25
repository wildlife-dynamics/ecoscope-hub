#!/bin/bash
#
# Copy the canonical dev scripts into each workflow repo's dev/ folder.
# The vendored copies are what CI invokes; this script keeps them in sync
# with the source of truth (this dir).
#
# Usage:
#   sync.sh                           # sync to all repos in DEFAULT_TARGETS
#   sync.sh <repo_path> [repo_path]   # sync to specified repo(s) only
#   sync.sh --check                   # exit non-zero if any target is out of sync

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Files to sync into each target's dev/ folder.
FILES=(recompile.sh pytest-cli.sh activate.sh)

# Default target list: workflow repos under ~/MEP/wt-workflows/.
# Edit this list as repos are added or removed.
DEFAULT_TARGETS=(
    "$HOME/MEP/wt-workflows/wt-ndvi"
    "$HOME/MEP/wt-workflows/wt-trajectory-map"
    "$HOME/MEP/wt-workflows/wt-hydrological-monitoring"
    "$HOME/MEP/wt-workflows/wt-download-events"
    "$HOME/MEP/wt-workflows/wt-download-patrols"
    "$HOME/MEP/wt-workflows/wt-download-subjects"
)

check_only=false
targets=()
for arg in "$@"; do
    case $arg in
        --check) check_only=true ;;
        -h|--help)
            sed -n '2,11p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) targets+=("$arg") ;;
    esac
done

if [ ${#targets[@]} -eq 0 ]; then
    targets=("${DEFAULT_TARGETS[@]}")
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
