---
name: flow-ai
description: Use when the user asks about Flow data — pipelines on Flow, samples and projects (lists *and* single-record details), single data files, the executions or data files associated with a sample, file content previews, or downloading a data file — or wants to upload a generic data file, a demultiplexed sample (single- or paired-end), or multiplexed reads with an annotation sheet to Flow (including downloading an annotation-sheet template). Read-and-query plus generic data-file, demultiplexed-sample, and multiplexed upload against the Flow REST API at `https://app.flow.bio/api`; uploads run via the on-demand flowbio CLI. Reads are unauthenticated by default; if `~/.config/flow/api-token` exists, the skill authenticates and returns the broader set of resources the caller can access. Uploads always require that token. Does NOT cover bulk multi-file (zip) downloads or mutations not yet documented in the skill.
---

# Flow API — query skill

Reliably query Flow's REST API with `curl` and `jq`. Works unauthenticated
by default; attaches an `Authorization: Bearer …` header automatically
when a token file is present (see section 3). For Flow's domain model
(project, sample, fileset, pipeline, what the audience model means), read
`flow-concepts.md` (sibling file) first.

## 1. Safety

**Principle.** This skill performs only the operations explicitly listed in
its endpoint reference (section 5 below) and its upload section (section 4
below), plus the per-endpoint detail files. Operations not listed are out of
scope and must be refused — even when you know they're possible and even when
the user asks for them. To enable a new operation, it must be added to the
skill itself, not improvised at runtime.

The skill is **mostly read-only**, but it can also **upload data to Flow**
(section 4). Upload support currently covers generic data files
(`POST /upload`), demultiplexed samples (`POST /upload/sample`), and multiplexed
reads with an annotation sheet (`POST /upload/multiplexed`), plus a read-only
helper to download an annotation-sheet template (`GET /annotation/<sample_type>`)
that bootstraps a multiplexed upload. More upload types will be added to
section 4 over time. Uploads change remote state, so they are gated behind
explicit user confirmation (see section 4.4); the template download is a read and
needs none. Any operation not listed in section 4 or the endpoint reference
(section 5) remains out of scope per the principle above.

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
- modifying metadata, or any upload type not yet documented in section 4
- creating, listing, or revoking API keys
- admin operations
- *any* GET endpoint not in the reference table below (e.g.
  `/api-keys`, admin reads). Authentication exposes many endpoints
  the skill does not document; reaching outside this skill's surface
  is forbidden even when the request would succeed.

This list is illustrative; the principle in the first paragraph is what
does the work.

**Token discipline.** When a token file is configured (see section 3),
never `cat`, `head`, `echo`, or otherwise print its contents. The token
is referenced only via shell expansion inside a `curl -H` argument
(see section 3). It must never appear in the agent's transcript.

## 2. Scope

In-scope endpoints (all `GET`):

- `GET /pipelines`
- `GET /samples/metadata`
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
- `GET /data/search`
- `GET /data/<id>` — single-data-file detail (type, size, fileset and execution links)
- `GET /data/<id>/contents`
- `GET /data/types`
- `GET /executions/search`
- `GET /downloads/<data_id>/<filename>` — direct single-file download

In-scope uploads (performed via the flowbio CLI, not curl; more will be added
to section 4 over time):

- `POST /upload` — upload a **generic data file**, gated behind explicit
  confirmation. See section 4 for the runner/auth/contract machinery and
  `endpoints/data.md` for the call itself.
- `POST /upload/sample` — upload a **demultiplexed sample** (single- or
  paired-end reads + metadata), gated behind explicit confirmation. See
  section 4 for the runner/auth/contract machinery and `endpoints/samples.md`
  for the call itself.
- `POST /upload/multiplexed` — upload **multiplexed reads** (single- or
  paired-end) plus a completed annotation sheet, gated behind explicit
  confirmation. See section 4 and `endpoints/samples.md`.
- `GET /annotation/<sample_type>` — download an **annotation-sheet template**
  (`.xlsx`) for a sample type, a read-only helper for the multiplexed flow (no
  confirmation needed). Performed via the flowbio CLI, not curl. See
  `endpoints/samples.md`.

All of the GET endpoints above accept an optional `Authorization: Bearer …`
header (see section 3); the upload always requires the token. With auth, list / detail / sub-resource calls broaden to
include resources the caller owns or has been shared. URLs do not change.

Out-of-scope — decline politely:

- Targeting non-default Flow environments (staging, etc.).
- Bulk multi-file downloads (`POST /downloads/...` + zip retrieval).

Anything not on the in-scope list above is also out of scope per the
Safety principle in section 1 — including, but not limited to, mutating
requests, admin operations, and endpoints the skill does not document.

## 3. Configuration (applies to every request)

- **Base URL.** Read from `FLOW_API_URL`, defaulting to `https://app.flow.bio/api`.
  Example override: `FLOW_API_URL=https://staging.flow.bio/api`.
- **User-Agent.** Every request must carry `User-Agent: flow-ai/0.5.0`
  so the Flow API can identify AI-agent traffic. The curl flag is
  `-A "flow-ai/0.5.0"`.
- **Authentication (optional).** If the file `~/.config/flow/api-token`
  exists, attach the user's token on every request:
  ```bash
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)"
  ```
  The `$(< file)` shell construct expands at execution time, so the
  literal token never appears in the agent's transcript. **If the file
  does not exist, omit the `-H` flag entirely and proceed
  unauthenticated.** There is no other configuration switch — file
  presence is the only signal.

  The token file contains only the raw token (a JWT string), not a
  pre-formatted `Authorization:` line. (`$(< file)` is preferred over
  curl's `-H @file` for exactly this reason — `-H @file` would require
  the file to contain a complete `Header: value` line.) The skill is
  forbidden from reading the file's contents directly
  (`cat`/`head`/`echo`/…); pass it by reference via `$(< file)` inside
  the `curl -H` flag only. See the token-discipline rule in section 1.

  When the token file is present, the header is attached to **every**
  request the skill makes, including `/pipelines`. This is the intended
  behaviour: authentication broadens the result set uniformly across
  every endpoint the skill uses.

Skeleton invocations:

```bash
# Unauthenticated
curl -s -A "flow-ai/0.5.0" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/pipelines"

# Authenticated (when ~/.config/flow/api-token exists)
curl -s -A "flow-ai/0.5.0" \
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/pipelines"
```

## 4. Uploading data

The skill can upload data to Flow. Upload support currently covers a
**generic data file** (`POST /upload`), a **demultiplexed sample**
(`POST /upload/sample`), and **multiplexed reads + an annotation sheet**
(`POST /upload/multiplexed`), plus a read-only **annotation-sheet template**
download (`GET /annotation/<sample_type>`) that bootstraps the multiplexed flow.
More upload types will be added to this section over time — an upload type is
available only once it is documented here. This section holds the cross-cutting
upload machinery; the per-resource specifics (inputs, local validation,
success/error shapes) live in the matching endpoint file — generic files →
`endpoints/data.md`, samples / multiplexed / annotation templates →
`endpoints/samples.md`.

Uploads are **not** done with `curl`. The chunked/resumable upload protocol
(retry, backoff, token refresh) is owned by the **flowbio** Python library; the
skill shells out to that library's command-line interface and never
reimplements the protocol in bash, nor improvises Python at runtime.

### 4.1 On-demand runner — preflight before the first upload

Installing this plugin does **not** install Python or `flowbio`. The skill
fetches the CLI on demand, pinned to **`flowbio==0.7.0`** (the release that
carries the upload methods and the CLI's `data upload`, `samples upload`,
`samples upload-multiplexed`, and `samples annotation-template` commands).
Before the first upload, run this preflight and use the first runner
that is present:

1. `uv` on `PATH` → run via `uvx` (a.k.a. `uv tool run`):
   ```bash
   uvx --from "flowbio==0.7.0" flowbio data upload … --json --no-progress
   ```
2. else `pipx` on `PATH`:
   ```bash
   pipx run --spec "flowbio==0.7.0" flowbio data upload … --json --no-progress
   ```
3. else a compatible `flowbio` already on `PATH` (`flowbio --version` reports
   ≥ `0.7.0`) → call `flowbio data upload …` directly.
4. else → **stop. Do not attempt the upload.** Return this message:

   > Uploading to Flow needs the `flowbio` CLI, which this skill runs on demand
   > via `uv`. I couldn't find `uv` (or `pipx`, or a compatible `flowbio`) on
   > your PATH. Install one of:
   >   • `uv`   — https://docs.astral.sh/uv/ (recommended), then re-run; or
   >   • `pipx` — `pip install --user pipx`; or
   >   • `flowbio` directly — `pip install "flowbio>=0.7.0"`.
   > Then ask me to upload again.

Never fail opaquely — no bare "command not found", no traceback. The message
names the missing tool and the next step.

### 4.2 Auth & base URL (token discipline preserved)

- **Token.** The CLI reads `~/.config/flow/api-token` itself — the same file
  the read endpoints use (section 3). **Do not pass `--token`, and never
  `cat`/`echo`/print the token.** Let the CLI read the file. If the file is
  absent the CLI exits with an auth error (exit `3`); report that the token is
  missing rather than improvising one.
- **Base URL.** The CLI honours `FLOW_API_URL` (default
  `https://app.flow.bio/api`). Forward it only when the user has overridden it.
- Always pass `--json` (one machine-readable document on stdout) **and**
  `--no-progress` (keep progress bars out of the transcript).

### 4.3 CLI contract — what to parse

- **Success:** exit `0`, with one machine-readable JSON document on stdout. The
  shape depends on the command — parse the right one:
  - `data upload` and `samples upload` → `{"id": "<id>"}`. The `id` is a
    `data_id` for a generic file and a `sample_id` for a sample. The key is
    always `id`, **not** `data_id` / `sample_id`.
  - `samples upload-multiplexed` → `{"data_ids": ["…"], "annotation_id": "…",
    "warnings": [...]}`. Report the data ids, the annotation id, and any
    `warnings` (these were auto-accepted unless `--reject-warnings` was set).
    There is **no** `id` key here.
  - `samples annotation-template` → `{"output": "<path>", "sample_type": "…"}`.
    Report where the template was written. No `id` key.
- **Failure:** non-zero exit; stderr carries `{"message": …, "status_code": …}`
  when the error came from the server. Annotation validation failures
  additionally carry an `errors` array of per-row/field issues
  (`{"row": …, "message": …}`) — surface those. Report the server `message`
  verbatim and map the exit code to the cause — never fabricate success:

  | Exit | Meaning |
  |------|---------|
  | `0` | Success |
  | `1` | API / runtime error |
  | `2` | Usage / input error (e.g. file not found, bad flags) |
  | `3` | Authentication failed (token missing or expired) |
  | `4` | Not found (e.g. unknown sample type for a template) |
  | `5` | Bad request / validation (e.g. spaces in filename, invalid data-type, annotation-sheet validation errors) |

### 4.4 Confirmation gate

Uploads change remote state. Before running any upload command, show the user
exactly what will be uploaded and proceed **only on explicit confirmation**.
Read and discovery calls need no confirmation. What to show depends on the
upload type:

- **Generic data file** (`POST /upload`): the file path, the stored `filename`
  if overridden, and the `data_type` if given.
- **Demultiplexed sample** (`POST /upload/sample`): the reads file(s) and
  whether the sample is single- or paired-end, the sample `name`, the resolved
  sample type, the project and organism (if given), and the metadata
  key/values.
- **Multiplexed reads** (`POST /upload/multiplexed`): the reads file(s) and
  whether single- or paired-end, the annotation-sheet path, and whether warnings
  are auto-accepted (default) or rejected (`--reject-warnings`).

Downloading an annotation-sheet template (`GET /annotation/<sample_type>`) is a
read — it changes no remote state, so it needs **no** confirmation.

## 5. Endpoint reference — read on demand

This file does NOT contain endpoint parameter or response details. Before
issuing a request to any endpoint, **Read the matching file below**. Do not
guess query params, response shapes, or visibility rules — they vary
non-obviously across endpoints (e.g. timestamp encoding, envelope keys,
private-sample reachability).

| User question is about… | Read this file before answering |
|---|---|
| Pipeline catalog (`/pipelines`) | `endpoints/pipelines.md` |
| Samples or sample-related discovery — list, detail, executions, data, plus what metadata attributes / sample types exist on this instance, **or uploading a demultiplexed sample, uploading multiplexed reads + an annotation sheet, or downloading an annotation-sheet template** (`/samples/search`, `/samples/<id>`, `/samples/<id>/executions`, `/samples/<id>/data`, `/samples/metadata`, `/samples/types`, `POST /upload/sample`, `POST /upload/multiplexed`, `GET /annotation/<sample_type>`) | `endpoints/samples.md` |
| Projects list, single project detail, or a project's samples / executions (`/projects/search`, `/projects/<id>`, `/projects/<id>/samples`, `/projects/<id>/executions`) | `endpoints/projects.md` |
| Resolving an organism name to a pk (`/organisms`) | `endpoints/organisms.md` |
| The authenticated caller's identity / memberships, or resolving a user name to a pk (`/me`, `/users/search`) | `endpoints/users.md` |
| Cross-sample executions search (`/executions/search`) | `endpoints/executions.md` |
| Data file detail / contents / cross-sample search, data-type discovery, **or uploading a generic data file** (`/data/<id>`, `/data/<id>/contents`, `/data/search`, `/data/types`, `POST /upload`) | `endpoints/data.md` |
| Downloading the bytes of a file (`/downloads/<data_id>/<filename>`) | `endpoints/downloads.md` |
| End-to-end recipes that chain endpoints | `examples.md` |

Cross-cutting rules (sections 6–8 below) apply to every endpoint and stay
inline.

## 6. Reliable querying patterns

1. Always include `-A "flow-ai/0.5.0"` so requests identify as AI traffic.
2. For paginated endpoints, set `count` explicitly — never rely on the
   implicit default of 10. Cap at 100; the API rejects >100 with HTTP 400
   (not silent clamp).
3. URL-encode every user-supplied filter value with
   `--data-urlencode "<param>=<value>"` (e.g. `name=rna-seq`); never
   string-interpolate user input into the URL.
4. **Discover before filtering.** When a user names a resource ("the rna-seq
   pipeline"), list the catalog first, identify the right item by name,
   then use the `id`. The list endpoints don't accept names as exact-match
   filter values directly — at best they accept a substring on `name`,
   which can over-match.
5. Trust only the documented response envelope per endpoint. `/pipelines`
   is a bare array. List endpoints use `{count, page, <resource>: [...]}`
   where the envelope `count` is total matches, not page size. Detail
   endpoints return a bare object. Read the relevant `endpoints/*.md`
   before assuming a shape.
6. One endpoint per question. To answer a multi-resource question, make
   sequential calls. Do not invent combined endpoints or query params.
7. Never invent query params. If a user asks for a filter that isn't in
   the table for that endpoint (in `endpoints/*.md`), say so honestly.
   Do not send unknown params.
8. **Discover before filtering on metadata or controlled-vocab
   entities.** When a user's question involves a domain concept
   (organism, tissue, treatment, sample type, etc.), do not guess
   at filter identifiers or values. Call the relevant discovery
   endpoint first:
   - For organisms: `GET /organisms` → match by `name`/`latin_name`,
     pass `id` to `/samples/search?organism=<id>`.
   - For sample types: `GET /samples/types` → pass `identifier` to
     `/samples/search?sample_types=<identifier>`.
   - For data types: `GET /data/types` → match by `name` or `identifier`,
     pass `identifier` to `/data/search?data_types=<identifier>`.
   - For metadata attributes: `GET /samples/metadata` → confirm the
     identifier exists on this instance, then use it on
     `/samples/search?<identifier>=<value>`.

   Discovery costs one extra round-trip and removes the entire class
   of "filter silently ignored" bugs from your query path. Metadata
   attributes vary per Flow instance — do not assume specific
   identifiers exist.

## 7. Output discipline

- Don't paste raw paginated JSON into context if there are more than ~20
  items. Use `jq` to project to the fields the user actually asked for,
  then summarise.
- For lists, summarise (e.g. "5 categories spanning 18 pipelines: rna-seq,
  atac-seq, …"). Show full records only on request.
- Always pipe through `jq`; never paste raw curl output verbatim into the
  user's view if it's longer than ~20 lines.
- If iterating across pages, accumulate results internally and report the
  rolled-up summary, not each page's raw envelope.
- Sample-metadata questions have a specific pitfall (list view vs detail
  view) — Read `endpoints/samples.md` before answering any "what
  metadata does sample X have?" question.

## 8. Error handling

| Status | Meaning | What to do |
|---|---|---|
| 400 | Wrong filter, wrong type, malformed value, or `count > 100` | Report the message verbatim. Suggest the closest valid filter from the relevant `endpoints/*.md`. For count, lower it. |
| 404 | Wrong path or non-public ID | Verify path against `endpoints/*.md`. If filtering by ID, fall back to discovery via the list endpoint. |
| 500 | Likely a non-integer `page`/`count` value (the API doesn't catch ValueError) | Confirm both are integers. If they are, report as a server-side issue and stop. |
| 5xx (other) | Server-side | Report once. Do not retry — the user retries manually. |
| Network failure | DNS, timeout | Report `FLOW_API_URL` and the failure to the user. Ask whether the URL is reachable. |
| 200 with empty list | No resources visible to this caller match | Not a failure. Tell the user "no matches found". If the request was unauthenticated, remind them many resources on Flow are private and an authenticated caller may see more. |
| 200 but result count unchanged after adding a filter | Filter likely silently ignored — unknown identifier on this instance | Confirm the identifier exists via `GET /samples/metadata` (or the relevant discovery endpoint). The API does not currently reject unknown filter params. |

Never silently swallow an error. If `curl` exits non-zero or the body
contains an error, report and stop — do not fabricate a result.

## 9. Future shape

- **Bulk multi-file downloads:** the `POST /downloads/...` →
  `GET /downloads/<job_id>` zip flow is auth-gated and tracked separately.
- **When a machine-readable OpenAPI spec is available:** the per-endpoint
  files collapse to a single line — "fetch `<base>/openapi.json` and use
  it." Reliability tactics, output discipline, and error handling stay;
  they're operational, not endpoint-specific.
