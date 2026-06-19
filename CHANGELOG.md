# Changelog

All notable changes to the `flow-ai` skill are documented here. Versions
follow [Semantic Versioning](https://semver.org/).

The canonical version is `plugins/flow-ai/.claude-plugin/plugin.json#version`.
The User-Agent string in `plugins/flow-ai/skills/flow-ai/SKILL.md`
(`flow-ai/<version>`) tracks it. Bump both together on every release.

## [0.7.0] — 2026-06-19

- Added **metadata value discovery**: the skill can now list the controlled
  value set for a metadata attribute via `GET /samples/metadata/<identifier>/options`.
  This closes the gap the docs previously flagged — `GET /samples/metadata`
  lists attribute *identifiers*, and this endpoint lists the legal *values* for
  an attribute whose `has_options` is `true`. The intended flow is
  discover-then-filter: confirm the attribute (`/samples/metadata`) → read its
  options (`/samples/metadata/<identifier>/options`) → filter
  `/samples/search?<identifier>=<value>` with an exact option value, avoiding
  the under-match risk of substring-guessing a value.
- **Behaviours documented** in `endpoints/samples.md`: public read (auth only
  broadens the set with the caller's own un-validated terms); the `validated`
  and `value` (substring) query params; the response envelope
  `{count, total_count, options}` where `count` is the post-filter total and
  `total_count` the pre-filter total; the **hard cap of 100 options with no
  pagination** (detect truncation by comparing `count` to the array length and
  narrow with `?value=`); and 404 on an unknown identifier. Creating, merging,
  editing, and deleting options are admin operations and remain out of scope.
- Updated the stale "no value discovery yet" notes in `endpoints/samples.md` to
  point at the new endpoint for `has_options=true` attributes, while keeping the
  free-text (`has_options=false`) sample-records workaround.
- Added eval 016 covering the discover-then-filter value-discovery flow.

## [0.6.0] — 2026-06-10

- Added **running pipelines** (FLOW-613): the skill can now kick off a pipeline
  execution and, on request, poll it to completion. This is the skill's first
  `curl`-based mutation (uploads use the flowbio CLI; running is a plain JSON
  `POST`). The run flow chains `GET /pipelines` → `GET /pipelines/<id>`
  (versions) → `GET /pipelines/versions/<id>` (run schema) →
  `POST /pipelines/versions/<id>/run`, then `GET /executions/<id>` for polling.
  Documented in `endpoints/pipelines.md` ("Running a pipeline", with the full
  schema→body mapping for every param type — string/number/boolean/hidden/data/csv,
  modes, and `from_fileset`/`from_execution` autofill) and `examples.md`
  (Examples 22–23).
- Added the read endpoints needed to run: `GET /pipelines/<id>` (a pipeline's
  versions) and `GET /pipelines/versions/<id>` (a version's run schema and
  available Nextflow versions), documented in `endpoints/pipelines.md`.
- Added `GET /executions/<id>` — single-execution detail used to poll a run
  (status, `?log=<offset>` tailing, `include`/`exclude`), documented in
  `endpoints/executions.md`.
- **Defaults:** when the user doesn't specify, the skill picks the most-recent
  pipeline version (`versions[0]`) and the first of the descending-sorted
  Nextflow versions (`nextflow_versions[0]`). Running **always requires the token** and is gated
  behind explicit confirmation; the run returns the execution id plus a link to
  the run in the UI (the web URL derived from the base URL by stripping `/api`).
  By default it does **not** poll.
- Cancelling executions remains out of scope.
- **Backend prerequisite:** the run endpoint must be reachable by `ai-agent`
  tokens (`@protected(scopes=[AI_AGENT_SCOPE])` on `run_pipeline` plus the
  AI-scope golden-file entry in `flow-api`) — the analogue of the FLOW-610
  upload change.
- Added evals 012–015 covering the run happy path, opt-in polling, the
  missing-required-param refusal, and the no-run-capability (403) path.

## [0.5.0] — 2026-06-09

- Added **multiplexed upload** (UC-4): multiplexed reads (single- or paired-end)
  plus a completed annotation sheet via the on-demand `flowbio` CLI
  (`flowbio samples upload-multiplexed`). The library validates and uploads the
  annotation **before** the reads, so an invalid sheet never wastes a reads
  upload. Warnings are auto-accepted by default and returned for display;
  `--reject-warnings` makes them fatal. Documented in `endpoints/samples.md`
  (`POST /upload/multiplexed`) and `examples.md` (Example 20).
- Added the **annotation-template helper** (UC-5): download the server-generated
  `.xlsx` annotation sheet for a sample type (`flowbio samples annotation-template`,
  defaulting to `generic`) to bootstrap a multiplexed upload. It is a read, so it
  needs no confirmation gate. Documented in `endpoints/samples.md`
  (`GET /annotation/<sample_type>`) and `examples.md` (Example 21).
- Recorded that the multiplexed and template commands return JSON shapes
  distinct from the single-file `{"id": …}` contract
  (`{"data_ids", "annotation_id", "warnings"}` and `{"output", "sample_type"}`),
  and that annotation validation errors surface per-row in the error JSON.
- Bumped the pinned library to **`flowbio==0.7.0`** (the release that ships the
  `samples upload-multiplexed` and `samples annotation-template` commands)
  across all upload docs, examples, and evals.
- Two new evaluations: `010-upload-multiplexed-with-warnings.json` and
  `011-download-annotation-template.json`.
- Bumped the User-Agent / canonical version to `flow-ai/0.5.0`.

## [0.4.0] — 2026-06-09

- Added **demultiplexed sample upload** (single-end and paired-end) via the
  on-demand `flowbio` CLI (`flowbio samples upload`), pinned to `flowbio==0.6.0`.
  Reuses the runner preflight, token discipline, confirmation gate, and
  exit-code contract introduced for data-file upload.
- Pre-flight discovery + validation before upload: resolves the sample type
  (`/samples/types`), checks the metadata attributes required for that type
  (`/samples/metadata`), and resolves organism (`/organisms`) and project
  (`/projects/search`) names to ids. Missing required metadata is caught before
  any upload.
- Documented the call in `endpoints/samples.md` (`POST /upload/sample`) and
  added an end-to-end recipe (`examples.md` Example 19).
- Two new evaluations: `008-upload-paired-end-sample.json` and
  `009-upload-sample-missing-required-metadata.json`.
- Bumped the User-Agent / canonical version to `flow-ai/0.4.0`.

## [0.3.0] — 2026-06-09

- Added **generic data-file upload** (`POST /upload`) via the on-demand
  `flowbio` CLI (`flowbio data upload`), pinned to `flowbio==0.6.0`. Introduced
  the cross-cutting upload machinery in `SKILL.md` §4: the `uv`/`uvx` → `pipx`
  → existing-`flowbio` runner preflight with a no-runner install message, token
  discipline (the CLI reads `~/.config/flow/api-token`; the token never enters
  the transcript), the confirmation gate for mutations, and the JSON /
  exit-code contract.
- Moved data uploads from the forbidden list into a scoped allowed surface;
  everything else stays read-only / forbidden.
- Two new evaluations: `006-upload-data-file.json` and
  `007-upload-no-runner.json`.
- Bumped the User-Agent / canonical version to `flow-ai/0.3.0`.

## [0.2.0] — 2026-05-22

Initial public release.

- Read-only access to the Flow REST API at `https://app.flow.bio/api`.
- Covered resources: pipelines, samples, projects, organisms, users,
  executions, data files, and direct single-file downloads.
- Optional authentication via `~/.config/flow/api-token`.
- Five rubric-graded evaluations under `skills/flow-ai/evals/`.
