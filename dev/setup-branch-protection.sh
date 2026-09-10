#!/usr/bin/env bash
#
# Apply QA-flow branch protection rulesets to a workflow repo.
#
# Reads JSON ruleset templates from ../resources/ and POSTs (or PUTs, if a
# ruleset with the same name already exists) them to the GitHub Rulesets API:
#   - resources/qa_main_branch_rules.json    -> targets ~DEFAULT_BRANCH
#   - resources/qa_staging_branch_rules.json -> targets refs/heads/staging
#
# Usage:
#   ./dev/setup-branch-protection.sh                # current repo (gh CLI auto-detect)
#   ./dev/setup-branch-protection.sh <owner/repo>   # explicit target
#
# Override required status check contexts (CSV, replaces JSON defaults):
#   MAIN_REQUIRED_CHECKS="check1,check2" \
#   STAGING_REQUIRED_CHECKS="check1" \
#   ./dev/setup-branch-protection.sh <owner/repo>
#
# Requires: gh CLI authenticated as a user with admin access; jq.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
resources_dir="$script_dir/../resources"
MAIN_RULES="$resources_dir/qa_main_branch_rules.json"
STAGING_RULES="$resources_dir/qa_staging_branch_rules.json"

REPO="${1:-${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}}"

for f in "$MAIN_RULES" "$STAGING_RULES"; do
  [ -f "$f" ] || { echo "ERROR: missing ruleset template: $f" >&2; exit 1; }
done

echo "==> Repo: $REPO"

# Strip server-set fields (id/source_type/source) and optionally replace the
# required_status_checks list with a CSV-derived array.
prepare_payload() {
  local file="$1"
  local checks_csv="${2:-}"

  local payload
  payload=$(jq 'del(.id, .source_type, .source)' "$file")

  if [ -n "$checks_csv" ]; then
    local checks_json
    checks_json=$(jq -nc --arg csv "$checks_csv" '
      $csv | split(",") | map({context: (. | gsub("^\\s+|\\s+$"; ""))})
    ')
    payload=$(echo "$payload" | jq --argjson c "$checks_json" '
      (.rules[] | select(.type == "required_status_checks").parameters.required_status_checks) |= $c
    ')
  fi

  echo "$payload"
}

apply_ruleset() {
  local payload="$1"
  local name
  name=$(echo "$payload" | jq -r .name)

  local existing_id
  existing_id=$(gh api "repos/$REPO/rulesets" \
    --jq ".[] | select(.name == \"$name\") | .id" 2>/dev/null || true)

  if [ -n "$existing_id" ]; then
    echo "==> Updating ruleset '$name' (id=$existing_id)"
    echo "$payload" | gh api --method PUT "repos/$REPO/rulesets/$existing_id" --input - --jq '"   ok: \(.name) (id=\(.id))"'
  else
    echo "==> Creating ruleset '$name'"
    echo "$payload" | gh api --method POST "repos/$REPO/rulesets" --input - --jq '"   ok: \(.name) (id=\(.id))"'
  fi
}

apply_ruleset "$(prepare_payload "$MAIN_RULES" "${MAIN_REQUIRED_CHECKS:-}")"
apply_ruleset "$(prepare_payload "$STAGING_RULES" "${STAGING_REQUIRED_CHECKS:-}")"

echo "==> Done. Verify in: https://github.com/$REPO/settings/rules"
