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
- `008-upload-paired-end-sample.json` — demultiplexed paired-end sample upload: sample-type / required-metadata / organism / project discovery and validation, confirmation gate, `flowbio samples upload` with `--reads1`/`--reads2`, `{"id":...}` / exit-code handling.
- `009-upload-sample-missing-required-metadata.json` — pre-flight catch: required metadata for the sample type is missing, so the skill names the gap and refuses to upload.
- `010-upload-multiplexed-with-warnings.json` — multiplexed reads + annotation-sheet upload: paired-end `flowbio samples upload-multiplexed`, annotation-first validation, warnings auto-accepted (no `--reject-warnings`), and the `{"data_ids", "annotation_id", "warnings"}` / exit-code handling.
- `011-download-annotation-template.json` — annotation-template helper: resolve the sample type, run `flowbio samples annotation-template -o <path>` (a read, no confirmation gate), and report where the `.xlsx` template was written.
- `012-run-pipeline-on-sample.json` — run a pipeline: discovery chain (catalog → versions → schema), default version + Nextflow version, sample-name resolution, schema→body bucketing (`params`/`data_params`/`csv_params`), confirmation gate, `curl` POST to `/pipelines/versions/<id>/run`, and reporting the execution id + UI link without polling.
- `013-run-pipeline-and-poll.json` — run + opt-in polling: resolve a *named* version, run, then poll `GET /executions/<id>` on a ≥60s cadence until terminal, surfacing the log on `ERROR`.
- `014-run-pipeline-missing-required-param.json` — defensive: a required param has no default and can't be inferred, so the skill names the gap and refuses to submit an incomplete run.
- `015-run-pipeline-no-capability.json` — defensive: the server returns 403 (`can_run_pipelines` false, or token scope not authorised); the skill reports it verbatim and stops without fabricating a run.

Evals 001-004 exercise the `/me`-precheck pattern introduced as a
defensive mitigation for the API's silent auth-degrade behaviour.
Eval 005 does not require auth and tests the sample-name-resolution
discovery chain. Evals 006-007 exercise the data-upload flow added in
`flow-ai/0.3.0`, covering both the happy path (upload via the
on-demand flowbio CLI) and the no-runner fallback. Evals 008-009
exercise the demultiplexed-sample upload flow added in `flow-ai/0.4.0`,
covering the happy path (discovery + paired-end upload) and the
missing-required-metadata pre-flight catch. Evals 010-011 exercise the
multiplexed upload flow added in `flow-ai/0.5.0`: the multiplexed reads +
annotation-sheet upload (with warnings auto-accepted) and the annotation-template
download helper that bootstraps it. Evals 012-015 exercise the
pipeline-running flow added in `flow-ai/0.6.0`: the happy path (discovery →
schema → resolve params → confirm → run → return id + UI link), opt-in polling,
and two defensive paths (missing required parameter, and a 403 when the caller
can't run pipelines).
