#!/usr/bin/env bash
# Auto-approve read-only Flow API calls made by the flow-ai skill, but only when
# the user has explicitly opted in. Without the opt-in the script makes no
# decision, so Claude Code's normal permission prompt still applies.
#
# A read is a curl carrying the flow-ai User-Agent, using --get, targeting
# flow.bio (or the FLOW_API_URL override), and NOT posting. Pipeline runs
# (-X POST) are deliberately excluded so they keep prompting.
#
# A PreToolUse allow suppresses the prompt for the whole Bash line, so a read
# that chains a second command (; && || `...`) must NOT match — otherwise the
# tail rides in unapproved. A single `| jq` pipe is the skill's own read
# formatting and stays allowed.

[[ "$FLOW_AI_AUTO_APPROVE_READS" == "1" ]] || exit 0

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)

if [[ "$command" == 'curl -s -A "flow-ai/'* \
   && "$command" == *--get* \
   && "$command" != *"-X POST"* \
   && "$command" != *";"* \
   && "$command" != *"&&"* \
   && "$command" != *"||"* \
   && "$command" != *'`'* \
   && ( "$command" == *flow.bio* || "$command" == *FLOW_API_URL* ) ]]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Flow API read (curl --get)"}}'
fi
