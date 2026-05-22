# Changelog

All notable changes to the `flow-ai` skill are documented here. Versions
follow [Semantic Versioning](https://semver.org/).

The canonical version is `plugins/flow-ai/.claude-plugin/plugin.json#version`.
The User-Agent string in `plugins/flow-ai/skills/flow-ai/SKILL.md`
(`flow-ai/<version>`) tracks it. Bump both together on every release.

## [0.2.0] — 2026-05-22

Initial public release.

- Read-only access to the Flow REST API at `https://app.flow.bio/api`.
- Covered resources: pipelines, samples, projects, organisms, users,
  executions, data files, and direct single-file downloads.
- Optional authentication via `~/.config/flow/api-token`.
- Five rubric-graded evaluations under `skills/flow-ai/evals/`.
