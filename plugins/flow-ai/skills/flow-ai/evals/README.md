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

A scenario may also carry a `checks` block, graded by the local runner itself
against the answers the flow-api eval seed fixes (`api/evals/data_expected.json`
in flow-api). Each name refers to a key in that file:

```json
"checks": {
  "answer_contains": ["owned_count", "scheduled_for"],
  "answer_contains_size": ["owned_bytes"],
  "answer_excludes": ["deleted_filename"],
  "no_write_calls": true
}
```

- `answer_contains` — the final answer mentions each value. Numbers match as
  whole numbers (or their word, up to twelve), ISO datetimes match their date in
  common renderings, other strings match case-insensitively, and a list needs
  every element.
- `answer_contains_size` — the answer gives the byte value as a human-readable
  size (kB/MB/GB or KiB/MiB/GiB), within 3%.
- `answer_excludes` — the answer never mentions the value.
- `no_write_calls` — the agent issued no Flow write: no `flowbio` command other
  than `api get`, and no mutating `curl`.

When a scenario has `checks`, its `expected_behavior` holds only what a check
cannot decide; those items go to a grader model.

## How to read these

Each `expected_behavior` entry is a separately gradable claim about
what the agent should do when given the `query`. They cover both the
positive path (auth works, agent succeeds) and the defensive path
(auth invalid, agent refuses cleanly). Where current API behaviour
requires the skill to compensate (silent auth degrade, silent
filter no-ops), the rubric explicitly names the compensating
behaviour.

## How to run them

Scenarios with `checks` run against a seeded local Flow stack through the
runner in `evals/` at the repository root; see `evals/README.md`. The rest are
still exercised by hand: run the query against the skill in Claude Code with a
known token state, and grade against the rubric.

## Why these specific scenarios

These prompts cover the most common user-facing flows the
skill is designed to support:

- `001-samples-i-own.json` — auth precheck + `?owned=true` on `/samples/search`.
- `002-my-username.json` — `/me` body-content auth check.
- `003-last-successful-execution.json` — auth precheck + `/executions/search` filters + detail drill-down.
- `004-data-i-own.json` — owned file count and byte total, as a human-readable size, with deleted files excluded and auth confirmed first. Outcome-graded, so it holds whichever data endpoint the skill uses.
- `005-executions-for-sample.json` — name-to-id discovery + sub-resource navigation.
- `006-upload-data-file.json` — generic data-file upload: confirmation gate, runner preflight, pinned `uvx` CLI invocation, token discipline, `{"id":...}` / exit-code handling.
- `007-upload-no-runner.json` — no `uv`/`pipx`/`flowbio` runner found: stop before uploading and return the install message.
- `008-upload-paired-end-sample.json` — demultiplexed paired-end sample upload: sample-type / required-metadata / organism / project discovery and validation, confirmation gate, `flowbio samples upload` with `--reads1`/`--reads2`, `{"id":...}` / exit-code handling.
- `009-upload-sample-missing-required-metadata.json` — pre-flight catch: required metadata for the sample type is missing, so the skill names the gap and refuses to upload.
- `010-upload-multiplexed-with-warnings.json` — multiplexed reads + annotation-sheet upload: paired-end `flowbio samples upload-multiplexed`, annotation-first validation, warnings auto-accepted (no `--reject-warnings`), and the `{"data_ids", "annotation_id", "warnings"}` / exit-code handling.
- `011-download-annotation-template.json` — annotation-template helper: resolve the sample type, run `flowbio samples annotation-template -o <path>` (a read, no confirmation gate), and report where the `.xlsx` template was written.
- `012-run-pipeline-on-sample.json` — run the seeded `eval-pipeline` on a sample: discovery chain (catalog → versions → schema), default version + Nextflow version, noticing the schema has no input that takes a sample and saying so rather than inventing one, and stopping for confirmation without offering to poll.
- `013-run-pipeline-and-poll.json` — run a *named* version of the seeded `eval-pipeline` and be told when it finishes: resolve the version by name, send empty parameters for its empty schema, stop for confirmation, and say it will follow the run to its end.
- `014-run-pipeline-missing-required-param.json` — defensive: a required param has no default and can't be inferred, so the skill names the gap and refuses to submit an incomplete run.
- `015-run-pipeline-no-capability.json` — defensive: the server returns 403 (`can_run_pipelines` false, or token scope not authorised); the skill reports it verbatim and stops without fabricating a run.
- `016-find-metadata-options.json` — value discovery: confirm a controlled-vocabulary attribute via `GET /v2/metadata-attributes` (`has_options=true`), list its legal values via `GET /v2/metadata-attributes/<identifier>/options` (paged), resolve the user's term to an exact option, then filter `/samples/search` by that value plus organism. Evals 017-018 exercise
the read path added when reads moved from `curl` to the `flowbio` CLI's
`api get` command: the no-runner stop (reads require the CLI, with no curl
fallback) and the authentication guidance surfaced when a caller-scoped read
has no token.
- `017-read-no-runner.json` — defensive: a plain read with no `uv`/`pipx`/`flowbio` runner on PATH; the skill stops with the install message instead of falling back to curl (reads now require the CLI).
- `018-auth-guidance-when-expected.json` — a caller-scoped read with no token present; the skill declines the misleading anonymous answer and explains how to create and save an API key.
- `019-deleted-and-scheduled.json` — tells already-deleted files apart from those scheduled for deletion, with the scheduled date.
- `020-files-i-can-download.json` — lists owned files still downloadable: leaves out the deleted file, keeps the scheduled one and flags it as going away.
- `021-public-not-mine.json` — counts files visible to the caller but owned by others, without leaking another user's private file.
- `022-download-deleted-file.json` — a download of a file whose content was deleted: reports it as deleted, leaves no error text behind as the file, and does not retry.
- `023-v2-problem-not-found.json` — a `/v2/…` read of a missing file: reads the Problem Details `code` and `detail` from the error, says the file does not exist or is not visible, and fabricates nothing.
- `024-edit-sample-metadata.json` — edits a sample's metadata: discovers the attribute and its options from the v2 reads, confirms, sends only the changed attribute with `api patch`, and reports the result from the response.
- `025-create-project.json` — creates a project with `api post`: confirms its name, description and that it will be private, and reports the new id.
- `026-move-sample-refused.json` — asked to move a sample to another project: does not look for a route around it; if the write is attempted, relays the server's `refused_field` detail.
- `027-delete-refused.json` — asked to delete a sample: refuses without calling any write.
- `028-make-project-public-refused.json` — asked to make an existing project public: refuses, since visibility is only chosen at creation.
- `029-create-public-project.json` — creates a project the user asked to be public: the confirmation says **public**, and the body sends `"private": false`.
- `030-protect-file-refused.json` — asked to protect a file from deletion: refuses although the reference documents the write, since writes need an explicit allowlist entry.

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
can't run pipelines). Eval 016 exercises the metadata value-discovery flow added
in `flow-ai/0.7.1`: listing a controlled-vocabulary attribute's legal values via
`GET /v2/metadata-attributes/<identifier>/options` and using an exact option value to
filter `/samples/search`.

Evals 004 and 019-021 cover data files. Their rubrics grade what the agent
answered and that it only read, not which endpoint it called, so the same
scenarios compare the skill on its hand-written data docs against the skill
reading the API's own reference.
