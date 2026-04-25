#!/bin/bash
#
# Run a workflow's CLI against a test case from test-cases.yaml.
#
# Run from inside a workflow repo. Uses the generated workflow's pixi env
# (ecoscope-workflows-*-workflow/pixi.toml) unless --no-pixi is passed.
#
# Usage:
#   pytest-cli.sh <workflow_name> --case <test_case>
#   pytest-cli.sh <workflow_name> --all
#
# Flags:
#   --no-pixi      Skip pixi run wrapper; assume active env has the workflow installed.
#   --skip-setup   Skip pixi update + setup-test.sh (playwright install).
#   --quiet, -q    Minimal output: only show pass/fail and errors.

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

workflow_name=$1
shift || true

skip_setup=false
no_pixi=false
run_all=false
quiet=false
test_case=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-setup) skip_setup=true; shift ;;
        --no-pixi)    no_pixi=true; shift ;;
        --all)        run_all=true; shift ;;
        --quiet|-q)   quiet=true; shift ;;
        --case)       test_case="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

usage() {
    cat <<EOF
Usage: $0 <workflow_name> <--all | --case test_case_name> [flags]
  --case <name>   Run a specific test case
  --all           Run all test cases for the workflow
  --no-pixi       Skip pixi run wrapper; assume active env has the workflow installed
  --skip-setup    Skip pixi update + setup-test.sh (playwright install)
  --quiet, -q     Minimal output: only show pass/fail and errors
EOF
}

if [ -z "$workflow_name" ]; then usage; exit 1; fi
if [ "$run_all" = false ] && [ -z "$test_case" ]; then
    echo "ERROR: Must specify either --all or --case <test_case_name>" >&2; usage; exit 1
fi
if [ "$run_all" = true ] && [ -n "$test_case" ]; then
    echo "ERROR: Cannot specify both --all and --case" >&2; exit 1
fi

workflow_dash=$(echo "$workflow_name" | tr '_' '-')
repo_root=$(pwd)
workflow_dir="${repo_root}/ecoscope-workflows-${workflow_dash}-workflow"
manifest_path="${workflow_dir}/pixi.toml"
test_cases_file="${repo_root}/test-cases.yaml"

if [ ! -d "$workflow_dir" ]; then
    echo "ERROR: generated workflow dir not found: $workflow_dir" >&2
    echo "Did you run recompile.sh first?" >&2
    exit 1
fi
if [ ! -f "$test_cases_file" ]; then
    echo "ERROR: test-cases.yaml not found at $test_cases_file" >&2
    exit 1
fi

if [ "$no_pixi" = true ]; then
    env_label="active shell ($(command -v python 2>/dev/null || echo 'no python on PATH'))"
    run_cmd() { eval "$@"; }
else
    if [ ! -f "$manifest_path" ]; then
        echo "ERROR: pixi.toml not found at $manifest_path" >&2; exit 1
    fi
    env_label="pixi($manifest_path)"
    run_cmd() { pixi run --manifest-path "$manifest_path" --locked -e default "$@"; }
fi

if [ "$quiet" = false ]; then
    echo "=========================================="
    echo "Workflow:  $workflow_name"
    echo "Mode:      $([ "$run_all" = true ] && echo "ALL test cases" || echo "case=$test_case")"
    echo "env:       $env_label"
    echo "=========================================="
fi

# Setup: pixi update + activate (graphviz/playwright). Skip if --skip-setup or --no-pixi.
if [ "$skip_setup" = false ] && [ "$no_pixi" = false ]; then
    [ "$quiet" = false ] && echo "Updating pixi env: $manifest_path"
    pixi update --manifest-path "$manifest_path"
    [ "$quiet" = false ] && echo "Running setup-test.sh (playwright install)..."
    run_cmd bash "$script_dir/setup-test.sh"
elif [ "$quiet" = false ]; then
    echo "Skipping setup (--skip-setup or --no-pixi)"
fi

run_single_test_case() {
    local test_case=$1

    if [ "$quiet" = false ]; then
        echo ""
        echo "=========================================="
        echo "Running test case: $test_case"
        echo "=========================================="
    fi

    if ! yq -e ".\"${test_case}\"" "$test_cases_file" > /dev/null 2>&1; then
        echo "✗ $test_case — ERROR: test case not found in $test_cases_file"
        return 1
    fi

    if yq -e ".\"${test_case}\" | has(\"mock_io\")" "$test_cases_file" > /dev/null 2>&1; then
        use_mock_io=$(yq ".\"${test_case}\".mock_io" "$test_cases_file")
    else
        use_mock_io="true"
    fi
    [ "$quiet" = false ] && echo "Mock IO mode: $use_mock_io"

    temp_base="${RUNNER_TEMP:-/tmp}"
    results_dir="${temp_base}/workflow-test-results/${workflow_name}/${test_case}"
    rm -rf "$results_dir"
    mkdir -p "$results_dir"
    [ "$quiet" = false ] && echo "Created results directory: $results_dir"

    export ECOSCOPE_WORKFLOWS_RESULTS="file://${results_dir}"

    params_file="${results_dir}/params.yaml"
    yq ".\"${test_case}\".params" "$test_cases_file" > "$params_file"

    if [ "$quiet" = false ]; then
        echo "Extracted params:"; cat "$params_file"; echo ""
        echo "Executing workflow..."
        echo "Results will be written to: $ECOSCOPE_WORKFLOWS_RESULTS"
    fi

    cd "$workflow_dir"
    workflow_underscore=$(echo "$workflow_name" | tr '-' '_')

    cmd="python -m ecoscope_workflows_${workflow_underscore}_workflow.cli run --config-file $params_file --execution-mode sequential"
    if [ "$use_mock_io" = "true" ]; then
        cmd="$cmd --mock-io"
    fi
    [ "$quiet" = false ] && echo "Command: $cmd"

    if [ "$quiet" = true ]; then
        if run_cmd "$cmd" > /dev/null 2>&1; then cmd_exit_code=0; else cmd_exit_code=$?; fi
    else
        if run_cmd "$cmd"; then cmd_exit_code=0; else cmd_exit_code=$?; fi
    fi

    cd "$repo_root"

    result_json="${results_dir}/result.json"
    if [ ! -f "$result_json" ]; then
        echo "✗ $test_case — result.json not found at $result_json"
        return 1
    fi

    [ "$quiet" = false ] && echo "" && echo "Validating result.json..."
    error_value=$(jq -r '.error // "null"' "$result_json")

    if [ "$error_value" != "null" ] || [ $cmd_exit_code -ne 0 ]; then
        echo "✗ $test_case — FAILED"
        if [ "$error_value" != "null" ]; then
            echo "  Error: $(jq -r '.error' "$result_json")"
        fi
        [ "$quiet" = false ] && echo "" && echo "Full result.json:" && cat "$result_json"
        return 1
    fi

    echo "✓ $test_case — passed"
    if [ "$quiet" = false ]; then
        echo ""; echo "Full result.json:"; cat "$result_json"
    fi
    return 0
}

if [ "$run_all" = true ]; then
    test_cases=($(yq 'keys | .[]' "$test_cases_file" | tr -d '"\r'))

    if [ ${#test_cases[@]} -eq 0 ]; then
        echo "ERROR: Found 0 test cases in $test_cases_file. Is yq installed?" >&2
        exit 1
    fi

    [ "$quiet" = false ] && echo "" && echo "Found ${#test_cases[@]} test cases: ${test_cases[*]}" && echo ""

    declare -a failed_cases passed_cases

    for test_case in "${test_cases[@]}"; do
        if run_single_test_case "$test_case"; then
            passed_cases+=("$test_case")
        else
            failed_cases+=("$test_case")
            true
        fi
    done

    echo ""
    echo "=========================================="
    echo "TEST SUMMARY"
    echo "=========================================="
    echo "Total:  ${#test_cases[@]}"
    echo "Passed: ${#passed_cases[@]}"
    echo "Failed: ${#failed_cases[@]}"
    echo ""

    if [ ${#passed_cases[@]} -gt 0 ]; then
        echo "✓ Passed:"; for c in "${passed_cases[@]}"; do echo "  - $c"; done; echo ""
    fi
    if [ ${#failed_cases[@]} -gt 0 ]; then
        echo "✗ Failed:"; for c in "${failed_cases[@]}"; do echo "  - $c"; done; echo ""
        exit 1
    fi
    echo "✓ All tests passed!"
else
    run_single_test_case "$test_case"
fi
