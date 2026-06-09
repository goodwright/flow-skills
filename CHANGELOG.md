# Changelog

All notable changes to the `flow-ai` skill are documented here. Versions
follow [Semantic Versioning](https://semver.org/).

The canonical version is `plugins/flow-ai/.claude-plugin/plugin.json#version`.
The User-Agent string in `plugins/flow-ai/skills/flow-ai/SKILL.md`
(`flow-ai/<version>`) tracks it. Bump both together on every release.

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
