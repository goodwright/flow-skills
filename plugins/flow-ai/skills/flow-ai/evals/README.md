# flow-ai skill evaluations

Data-driven scenario evaluations for the `flow-ai` Claude Code skill.
Follows [Anthropic's skill-evaluation
format](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration):

```json
{
  "skills": ["flow-ai"],
  "query": "the user-facing prompt",
  "files": ["optional fixture file paths"],
  "expected_behavior": [
    "individual rubric items, gradable as pass/fail"
  ]
}
```

Each eval is a single JSON file; one scenario per file for clarity in
review.

## How to read these

Each `expected_behavior` entry is a separately gradable claim about
what the agent should do when given the `query`. They cover both the
positive path (auth works, agent succeeds) and the defensive path
(auth invalid, agent refuses cleanly). Where current API behaviour
requires the skill to compensate (silent auth degrade, silent
filter no-ops), the rubric explicitly names the compensating
behaviour.

## How to run them

Anthropic does not ship a built-in runner. Today these are exercised
manually — pick an eval, run the query against the skill in Claude
Code with a known token state, and grade against the rubric.

When a runner is built (likely a thin wrapper around the existing
`skill-tests/` harness — see issue tracker), each rubric item becomes
a separate assertion against the agent's tool-call trace.

## Why these specific scenarios

These prompts cover the most common user-facing flows the
skill is designed to support:

- `001-samples-i-own.json` — auth precheck + `?owned=true` on `/samples/search`.
- `002-my-username.json` — `/me` body-content auth check.
- `003-last-successful-execution.json` — auth precheck + `/executions/search` filters + detail drill-down.
- `004-data-i-own.json` — auth precheck + `/data/search?owned=true` + size aggregation.
- `005-executions-for-sample.json` — name-to-id discovery + sub-resource navigation.
- `006-upload-data-file.json` — generic data-file upload: confirmation gate, runner preflight, pinned `uvx` CLI invocation, token discipline, `{"id":...}` / exit-code handling.
- `007-upload-no-runner.json` — no `uv`/`pipx`/`flowbio` runner found: stop before uploading and return the install message.

Evals 001-004 exercise the `/me`-precheck pattern introduced as a
defensive mitigation for the API's silent auth-degrade behaviour.
Eval 005 does not require auth and tests the sample-name-resolution
discovery chain. Evals 006-007 exercise the data-upload flow added in
`flow-ai/0.3.0`, covering both the happy path (upload via the
on-demand flowbio CLI) and the no-runner fallback.
