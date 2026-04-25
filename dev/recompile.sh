#!/bin/bash
#
# Recompile a workflow repo from spec.yaml.
#
# Run from inside a workflow repo (the dir containing spec.yaml + pixi.toml).
# Uses the repo's own pixi env (which provides wt-compiler) unless --no-pixi
# is passed, in which case it calls wt-compiler directly off PATH (e.g. when
# running from inside an env like `pixi shell -w ecoscope-tasks` that has
# wt-compiler installed editable).
#
# Usage: recompile.sh [--no-pixi] [compiler-flags...]

set -e

no_pixi=false
compiler_flags=()
for arg in "$@"; do
    case $arg in
        --no-pixi) no_pixi=true ;;
        *) compiler_flags+=("$arg") ;;
    esac
done

if [ ! -f spec.yaml ]; then
    echo "ERROR: spec.yaml not found in $(pwd). Run from inside a workflow repo." >&2
    exit 1
fi

if [ "$no_pixi" = true ]; then
    echo "env: active shell ($(command -v wt-compiler 2>/dev/null || echo 'wt-compiler not on PATH'))"
    run_cmd() { "$@"; }
else
    if [ ! -f pixi.toml ]; then
        echo "ERROR: pixi.toml not found in $(pwd). Pass --no-pixi or activate an env with wt-compiler." >&2
        exit 1
    fi
    echo "env: pixi($(pwd)/pixi.toml)"
    run_cmd() { pixi run --manifest-path pixi.toml "$@"; }
    pixi update --manifest-path pixi.toml
fi

# (re)initialize dot executable to ensure graphviz is available
run_cmd dot -c

flags="${compiler_flags[*]}"
echo "recompiling spec.yaml with flags '--clobber ${flags}'"

run_cmd wt-compiler compile \
  --spec spec.yaml \
  --pkg-name-prefix=ecoscope-workflows \
  --results-env-var=ECOSCOPE_WORKFLOWS_RESULTS \
  --clobber ${flags}
