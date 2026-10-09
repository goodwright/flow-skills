# flow-ai — data reference pilot and local eval runner

**Ticket:** FLOW-754 follow-on; first capability migrated under flow-api's
`docs/ai-integration/architecture.md` (self-describing API).
**Depends on:** flow-api's `docs/superpowers/specs/2026-10-09-v2-reference-data-pilot-design.md`,
which provides `/v2/reference`, `/v2/reference/data`, and the eval seed in
`api/evals/`.

## Goal

The skill learns about Flow data files from the API's own reference instead of
the hand-written `endpoints/data.md`. A local eval runner shows, with numbers,
that agents do at least as well that way, on a frontier model and on a small one.

## What the API provides

- `GET /v2/reference`: an index page with what Flow is, the auth levels,
  conventions (string ids, error envelope, pagination, list grammar, datetimes)
  and a link to each topic.
- `GET /v2/reference/data`: the data topic's concepts and every data operation
  in full: `GET /v2/data` (list), `GET /v2/data/{data_id}`,
  `PATCH /v2/data/{data_id}`.
- Both are anonymous `text/markdown`, fetched with
  `flowbio api get /v2/reference/data`. Links in them are absolute API paths.
- `api/evals/seed_data_evals.py` seeds a local stack with the user `eval-agent`,
  its files (including one deleted and one scheduled for deletion), and other
  users' files. It writes an `ai-agent` token to `EVAL_TOKEN_FILE`.
  `api/evals/data_expected.json` holds the answers the graders check.

## Part 1 — the local eval runner

Lives at `evals/` in the repository root, as a small uv project. It runs the
plugin's scenarios against a local Flow stack.

### Running a scenario

For each scenario selected by `--scenario <glob>` and each `--model` given
(default: a frontier model and a small one):

1. Create an empty temporary working directory.
2. Run `claude -p "<query>"` there with:
   - `--plugin-dir plugins/flow-ai`, so only the plugin under test is loaded
   - `--model <model>`
   - `--output-format stream-json --verbose`, which captures every tool call
   - `--setting-sources project` and `--strict-mcp-config`, so the developer's
     own CLAUDE.md, plugins and MCP servers do not leak in
   - `--allowedTools` set to the skill's recommended read allowlist
     (`flowbio api get` and `jq`), so a write would stall rather than run.
3. Set `FLOW_API_URL` to the local stack (default `http://localhost:8019`) and
   `FLOW_API_TOKEN` from `EVAL_TOKEN_FILE` in the child's environment only. The
   runner never prints the token.
4. Save the transcript to `evals/runs/<timestamp>/<scenario>-<model>.jsonl`
   (gitignored).

### Metrics, read from the transcript

- pass/fail per rubric item, and overall
- number of Flow calls, and the paths called, in order
- input and output tokens, and turns.

### Grading

- **Deterministic checks first.** A scenario may declare `checks` that the
  runner evaluates itself:
  - `answer_contains`: values from `data_expected.json`, referenced by key
  - `answer_excludes`: for example, the deleted filename in a "which files can
    I download" answer
  - `no_write_calls`
- **The rubric second.** Any `expected_behavior` items not covered by a check go
  to a second `claude -p` call, which grades the final answer and the call list
  against them and returns pass/fail per item as JSON.

### Output

A table per run: scenario × model with pass rate, Flow calls and tokens. The
runner also writes `summary.json`, so the before and after runs can be compared
with `evals/compare.py before after`.

Subscription limits make each run a deliberate act, so there is no
"run everything" default. A scenario filter is required.

## Part 2 — data scenarios

Scenario JSON gains an optional `checks` block; existing files stay valid.
**Rubrics are outcome-based and path-agnostic.** They grade what the agent
answered and whether it read only, not which endpoint it used, so the same
scenario grades the legacy-docs "before" run and the reference "after" run
fairly.

- **004-data-i-own** (revised): "How much data do I own on Flow?"
  - checks: owned count and bytes from `data_expected.json`, human-readable size
  - rubric: confirms auth first; says whether it counted files or bytes;
    excludes deleted files or says they are excluded
- **019-deleted-and-scheduled**: "Which of my files have been deleted, and are
  any about to be?"
  - checks: the deleted filename and the scheduled filename, with its date
- **020-files-i-can-download**: "List the files I own that I can still
  download."
  - checks: excludes the deleted filename; includes the scheduled one, flagged
    as going away
- **021-public-not-mine**: "How many files can I see that I don't own?"
  - checks: the public-but-not-owned count; never mentions the other user's
    private file.

## Part 3 — the skill edits

- **`SKILL.md`**
  - Add a short "Finding out about the API" section: for data files, read
    `GET /v2/reference/data` before calling any data endpoint. Follow its links
    rather than guessing paths or parameters. What it says overrides prior
    knowledge.
  - In the routing table, the data row points at `/v2/reference/data` for
    listing, searching and reading one file. It keeps `endpoints/data.md` only
    for what is still legacy: `/data/<id>/contents`, `/data/types` and uploads.
  - Remove `/data/search` and `/data/<id>` from the envelope and shape tables
    (lines ~171–193). The reference states the v2 shapes.
- **`endpoints/data.md`**: delete the `GET /data/<id>` section and every
  `/data/search` mention. The remainder is the transitional `legacy/` content
  for this capability.
- **`flow-concepts.md`**: drop the single-data-file detail paragraph (~254),
  which the data topic's concepts now cover.
- **`safety.md`**: replace `GET /data/search` and `GET /data/<id>` in the read
  list with `GET /v2/reference…`, `GET /v2/data` and `GET /v2/data/{id}`.
  `PATCH /v2/data/{id}` is a write and follows the confirm-before-write rule.
- **`examples.md`**: update any recipe that lists or reads data files to the v2
  paths, or delete it if the reference makes it redundant.

## Order of work

1. Build the runner and the four scenarios. Check the pinned `flowbio==0.9.0`
   passes a `text/markdown` body through `api get` unchanged; if it does not,
   bump the pin first.
2. Bring up flow-api's local stack on a branch with the reference merged, run
   the seed, and take the **before** run: the current skill, scenarios
   004/019–021, both models.
3. Make the skill edits.
4. Take the **after** run. The edits ship only if the after pass rate is at
   least the before pass rate on both models, at no worse token cost. Otherwise
   the finding goes back to flow-api as a reference or API fix, not a skill
   workaround.
5. Record the before and after table in the pull request.

## Out of scope

- Other capabilities, the `legacy/` directory restructure, the ≤ 100-line
  `SKILL.md`, the flowbio major-range pin.
- Running evals in CI.
- Consolidating flow-api's `skill-tests/` harness.
