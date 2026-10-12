# Safety — the full allowlist

`SKILL.md` carries the short form of this rule. This file is the long form:
the reasoning behind it, the illustrative refusals, and the complete
in-scope endpoint list.

## The principle

**Principle.** This skill performs only the operations explicitly listed in
its endpoint reference (the endpoint table in `SKILL.md`) and its upload section (`uploading.md`), plus the per-endpoint detail files. Operations not listed are out of
scope and must be refused — even when you know they're possible and even when
the user asks for them. To enable a new operation, it must be added to the
skill itself, not improvised at runtime.

The skill is **mostly read-only**, but it has two families of mutation. It can
**run pipelines** (`POST /pipelines/versions/<id>/run`, via `curl` — see
`endpoints/pipelines.md`), and it can **upload data to Flow** (`uploading.md`).
Upload support currently covers generic data files (`POST /upload`),
demultiplexed samples (`POST /upload/sample`), and multiplexed reads with an
annotation sheet (`POST /upload/multiplexed`), plus a read-only helper to
download an annotation-sheet template (`GET /annotation/<sample_type>`) that
bootstraps a multiplexed upload. More upload types will be added to `uploading.md`
over time. Both running and uploading change remote state, so they are gated
behind explicit user confirmation (the run confirmation lives in
`endpoints/pipelines.md`; the upload confirmation in the confirmation gate in `uploading.md`); reads such as
the template download need none. Any operation not listed in `uploading.md`, the run
flow in `endpoints/pipelines.md`, or the endpoint reference (section 5) remains
out of scope per the principle above.

The principle is verb-agnostic. Authentication does not change it: the
same rules apply whether the token file is present or absent. Authentication
only broadens the *data* the allowed operations return; it never expands
the set of allowed operations itself.

**Illustrative (non-exhaustive) operations that are *not* in the
allowlist today** and must be refused if asked:

- deleting samples, projects, data, or executions
- sharing a resource or changing its permissions
- transferring ownership
- making data public or private
- cancelling an execution
- modifying metadata, or any upload type not yet documented in `uploading.md`
- protecting a data file from deletion, or lifting that protection
  (`PATCH /v2/data/<id>`)
- creating, listing, or revoking API keys
- admin operations
- *any* GET endpoint not in the endpoint table in `SKILL.md` (e.g.
  `/api-keys`, admin reads). Authentication exposes many endpoints
  the skill does not document; reaching outside this skill's surface
  is forbidden even when the request would succeed.

This list is illustrative; the principle in the first paragraph is what
does the work.

**The API's reference describes writes too.** `GET /v2/reference/<topic>`
documents every operation of a topic, including ones that change remote state,
such as `PATCH /v2/data/<id>`. Reading about an operation there does not make
it allowed: only the operations listed below may be called.

**Token discipline.** When a token file is configured (see `SKILL.md` step 0),
never `cat`, `head`, `echo`, or otherwise print its contents. Reads and
uploads never handle the token at all — the flowbio CLI reads the file
itself (never pass `--token`). The only places the skill references the
token directly are the two `curl` remnants — the pipeline run
(`endpoints/pipelines.md`) and an authenticated file download
(`endpoints/downloads.md`) — and there only via shell expansion
(`$(< ~/.config/flow/api-token)`) inside a `-H` argument. In every case
the token must never appear in the agent's transcript.

## Full scope

In-scope endpoints (all `GET`):

- `GET /pipelines`
- `GET /pipelines/<id>` — single-pipeline detail (versions list)
- `GET /pipelines/versions/<id>` — pipeline-version detail (run schema)
- `GET /samples/metadata`
- `GET /samples/metadata/<identifier>/options` — controlled value set for one metadata attribute (value discovery)
- `GET /samples/types`
- `GET /samples/types/<identifier>`
- `GET /samples/search`
- `GET /samples/<id>` — single-sample detail (full metadata bag, inlined filesets)
- `GET /samples/<id>/executions`
- `GET /samples/<id>/data`
- `GET /projects/search`
- `GET /projects/<id>` — single-project detail (description, papers, owner)
- `GET /projects/<id>/samples` — samples in a project
- `GET /projects/<id>/executions` — executions in a project
- `GET /organisms`
- `GET /organisms/<id>`
- `GET /me`
- `GET /users/search`
- `GET /v2/reference`, `GET /v2/reference/<topic>` — the API's own reference pages
- `GET /v2/data` — list, filter and count data files
- `GET /v2/data/<id>` — single-data-file detail
- `GET /data/<id>/contents`
- `GET /data/types`
- `GET /executions/search`
- `GET /executions/<id>` — single-execution detail (poll a run, drill into a run)
- `GET /downloads/<data_id>/<filename>` — direct single-file download

In-scope mutation (performed via `curl`, gated behind explicit confirmation):

- `POST /pipelines/versions/<id>/run` — **run a pipeline version**. Unlike the
  uploads below, this is a plain JSON `POST` done with `curl` (no chunked-upload
  protocol, no flowbio CLI). It always requires the token and is gated behind
  the confirmation rule. See `endpoints/pipelines.md` for the full run flow,
  the schema→body mapping, and error handling.

In-scope uploads (performed via the flowbio CLI, not curl; more will be added
to `uploading.md` over time):

- `POST /upload` — upload a **generic data file**, gated behind explicit
  confirmation. See `uploading.md` for the runner/auth/contract machinery and
  `endpoints/data.md` for the call itself.
- `POST /upload/sample` — upload a **demultiplexed sample** (single- or
  paired-end reads + metadata), gated behind explicit confirmation. See
  `uploading.md` for the runner/auth/contract machinery and `endpoints/samples.md`
  for the call itself.
- `POST /upload/multiplexed` — upload **multiplexed reads** (single- or
  paired-end) plus a completed annotation sheet, gated behind explicit
  confirmation. See `uploading.md` and `endpoints/samples.md`.
- `GET /annotation/<sample_type>` — download an **annotation-sheet template**
  (`.xlsx`) for a sample type, a read-only helper for the multiplexed flow (no
  confirmation needed). Performed via the flowbio CLI, not curl. See
  `endpoints/samples.md`.

All of the GET endpoints above are issued via `flowbio api get` (see
`SKILL.md` step 0), which attaches the caller's token automatically when the token
file is present; the upload always requires the token. With auth, list /
detail / sub-resource calls broaden to include resources the caller owns or
has been shared. Paths do not change.

Out-of-scope — decline politely:

- Targeting non-default Flow environments (staging, etc.).
- Bulk multi-file downloads (`POST /downloads/...` + zip retrieval).

Anything not on the in-scope list above is also out of scope per the
Safety principle in this file — including, but not limited to, mutating
requests, admin operations, and endpoints the skill does not document.


## Future shape

- **Bulk multi-file downloads:** the `POST /downloads/...` →
  `GET /downloads/<job_id>` zip flow is auth-gated and tracked separately.
- **When a machine-readable OpenAPI spec is available:** the per-endpoint
  files collapse to a single line — "fetch `<base>/openapi.json` and use
  it." Reliability tactics, output discipline, and error handling stay;
  they're operational, not endpoint-specific.
