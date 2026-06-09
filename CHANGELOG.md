# Changelog

All notable changes to the `flow-ai` skill are documented here. Versions
follow [Semantic Versioning](https://semver.org/).

The canonical version is `plugins/flow-ai/.claude-plugin/plugin.json#version`.
The User-Agent string in `plugins/flow-ai/skills/flow-ai/SKILL.md`
(`flow-ai/<version>`) tracks it. Bump both together on every release.

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
