---
name: flow-ai
description: Use when the user asks about Flow data — pipelines on Flow, samples and projects (lists *and* single-record details), single data files, the executions or data files associated with a sample, file content previews, or downloading a data file — or wants to run a pipeline on Flow (kick off an execution and optionally poll it), or to upload a generic data file, a demultiplexed sample (single- or paired-end), or multiplexed reads with an annotation sheet (including downloading an annotation-sheet template). Reads, queries and uploads use the on-demand flowbio CLI (reads via `api get`); pipeline runs and file downloads use curl, against the Flow REST API at `https://app.flow.bio/api`. Reads are unauthenticated by default; if `~/.config/flow/api-token` exists, the CLI authenticates and returns resources the caller can access. Running pipelines and uploads require that token and are gated behind explicit confirmation. Does NOT cover bulk multi-file (zip) downloads, cancelling executions, or undocumented mutations.
---

# Flow API — query skill

Reliably query Flow's REST API through the `flowbio` CLI's read-only
`api get` command, projecting the results with `jq`. Works unauthenticated
by default; the CLI attaches the caller's token automatically when a token
file is present (see section 3). For Flow's domain model (project, sample,
fileset, pipeline, what the audience model means), read `flow-concepts.md`
(sibling file) first.

## 1. Safety

**Principle.** This skill performs only the operations explicitly listed in
its endpoint reference (section 5 below) and its upload section (section 4
below), plus the per-endpoint detail files. Operations not listed are out of
scope and must be refused — even when you know they're possible and even when
the user asks for them. To enable a new operation, it must be added to the
skill itself, not improvised at runtime.

The skill is **mostly read-only**, but it has two families of mutation. It can
**run pipelines** (`POST /pipelines/versions/<id>/run`, via `curl` — see
`endpoints/pipelines.md`), and it can **upload data to Flow** (section 4).
Upload support currently covers generic data files (`POST /upload`),
demultiplexed samples (`POST /upload/sample`), and multiplexed reads with an
annotation sheet (`POST /upload/multiplexed`), plus a read-only helper to
download an annotation-sheet template (`GET /annotation/<sample_type>`) that
bootstraps a multiplexed upload. More upload types will be added to section 4
over time. Both running and uploading change remote state, so they are gated
behind explicit user confirmation (the run confirmation lives in
`endpoints/pipelines.md`; the upload confirmation in section 4.4); reads such as
the template download need none. Any operation not listed in section 4, the run
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
never `cat`, `head`, `echo`, or otherwise print its contents. Reads and
uploads never handle the token at all — the flowbio CLI reads the file
itself (never pass `--token`). The only place the skill references the
token directly is the pipeline-run `curl` (section 5 and
`endpoints/pipelines.md`), and there only via shell expansion
(`$(< ~/.config/flow/api-token)`) inside a `-H` argument. In every case
the token must never appear in the agent's transcript.

## 2. Scope

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
- `GET /data/search`
- `GET /data/<id>` — single-data-file detail (type, size, fileset and execution links)
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

All of the GET endpoints above are issued via `flowbio api get` (see
section 3), which attaches the caller's token automatically when the token
file is present; the upload always requires the token. With auth, list /
detail / sub-resource calls broaden to include resources the caller owns or
has been shared. Paths do not change.

Out-of-scope — decline politely:

- Targeting non-default Flow environments (staging, etc.).
- Bulk multi-file downloads (`POST /downloads/...` + zip retrieval).

Anything not on the in-scope list above is also out of scope per the
Safety principle in section 1 — including, but not limited to, mutating
requests, admin operations, and endpoints the skill does not document.

## 3. Configuration (applies to every read)

Reads are issued with the flowbio CLI's read-only `api get` command:

```
flowbio api get <PATH> [--param KEY=VALUE …] --json
```

Substitute your resolved runner for the bare `flowbio` (see the runner
preflight in section 4.1 — the same machinery serves reads and uploads):
`uvx --from "flowbio==0.9.0" flowbio api get …`, or the `pipx run` form, or a
compatible `flowbio` already on `PATH`. If no runner is found, stop — reads
need the CLI just as uploads do (section 4.1).

- **`<PATH>`.** Relative to the base URL, leading slash optional (e.g.
  `/samples/search`). Never put a `?` in the path — the CLI rejects it; pass
  query params with `--param`.
- **Query params.** One `--param KEY=VALUE` per param; the CLI URL-encodes each
  value. Repeat the flag for multi-valued params
  (`--param sample_types=rna --param sample_types=atac`). Never interpolate
  user input into the path.
- **`--json`.** Always pass it. For `api get` it does **not** reshape the
  success body — that stays the raw response for `jq` to project — it only
  makes error output machine-readable (see section 8).
- **Base URL.** The CLI resolves it from `FLOW_API_URL` (default
  `https://app.flow.bio/api`). Forward `FLOW_API_URL` only when the user has
  overridden it; never pass `--base-url` otherwise.
- **Output.** The raw body goes to stdout — pipe it through `jq` exactly as
  before.

**Authentication.** The CLI reads the token from `~/.config/flow/api-token`
itself. When the file is present every read is authenticated and broadens
uniformly across every endpoint; when it is absent the CLI reads anonymously
(public resources only). File presence is the only switch — **never pass
`--token`, and never `cat`/`head`/`echo`/print the token** (section 1).

If a read fails authentication, or the user's request implies they expect to
be authenticated (e.g. "my samples", `owned=true`) but no token file is
present, tell them how to authenticate rather than silently proceeding
anonymously: create an API key in the Flow web app (Settings →
Account Management → API Keys, purpose "AI Agent") and save it to
`~/.config/flow/api-token` (or set `FLOW_API_TOKEN`). The `README.md`
"Getting a Flow API key" section has the exact steps.

Skeleton invocations (using `uvx` as the resolved runner):

```bash
# Reads anonymously, or with the caller's token if ~/.config/flow/api-token exists
uvx --from "flowbio==0.9.0" flowbio api get /pipelines --json

# With query params
uvx --from "flowbio==0.9.0" flowbio api get /samples/search \
  --param name=rna-seq --param count=20 --json | jq '.count'
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

### 4.1 On-demand runner — preflight before the first CLI call

Installing this plugin does **not** install Python or `flowbio`. The skill
fetches the CLI on demand, pinned to **`flowbio==0.9.0`** (the release that
carries the read-only `api get` command **and** the upload commands `data
upload`, `samples upload`, `samples upload-multiplexed`, and `samples
annotation-template`). The CLI is required for **both reads and uploads** —
there is no curl fallback for reads. Before the first CLI call of a session
(read or upload), run this preflight and use the first runner that is present:

1. `uv` on `PATH` → run via `uvx` (a.k.a. `uv tool run`):
   ```bash
   uvx --from "flowbio==0.9.0" flowbio <command> …
   ```
2. else `pipx` on `PATH`:
   ```bash
   pipx run --spec "flowbio==0.9.0" flowbio <command> …
   ```
3. else a compatible `flowbio` already on `PATH` (`flowbio --version` reports
   ≥ `0.9.0`) → call `flowbio <command> …` directly.
4. else → **stop. Do not attempt the call.** Return this message:

   > Using Flow needs the `flowbio` CLI, which this skill runs on demand
   > via `uv`. I couldn't find `uv` (or `pipx`, or a compatible `flowbio`) on
   > your PATH. Install one of:
   >   • `uv`   — https://docs.astral.sh/uv/ (recommended), then re-run; or
   >   • `pipx` — `pip install --user pipx`; or
   >   • `flowbio` directly — `pip install "flowbio>=0.9.0"`.
   > Then ask me again.

The `<command>` is `api get …` for reads (section 3) and `data upload …`,
`samples upload …`, etc. for uploads (sections 4.3–4.4). Whichever runner
resolves, use it consistently for every call — the prefix is stable, which is
what lets the operator allowlist it (see `README.md`). Never fail opaquely —
no bare "command not found", no traceback. The message names the missing tool
and the next step.

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
| Pipeline catalog, a pipeline's versions, a version's run schema, **or running a pipeline** (`/pipelines`, `/pipelines/<id>`, `/pipelines/versions/<id>`, `POST /pipelines/versions/<id>/run`) | `endpoints/pipelines.md` |
| Samples or sample-related discovery — list, detail, executions, data, plus what metadata attributes / sample types exist on this instance and the legal values for a controlled-vocabulary attribute, **or uploading a demultiplexed sample, uploading multiplexed reads + an annotation sheet, or downloading an annotation-sheet template** (`/samples/search`, `/samples/<id>`, `/samples/<id>/executions`, `/samples/<id>/data`, `/samples/metadata`, `/samples/metadata/<identifier>/options`, `/samples/types`, `POST /upload/sample`, `POST /upload/multiplexed`, `GET /annotation/<sample_type>`) | `endpoints/samples.md` |
| Projects list, single project detail, or a project's samples / executions (`/projects/search`, `/projects/<id>`, `/projects/<id>/samples`, `/projects/<id>/executions`) | `endpoints/projects.md` |
| Resolving an organism name to a pk (`/organisms`) | `endpoints/organisms.md` |
| The authenticated caller's identity / memberships, or resolving a user name to a pk (`/me`, `/users/search`) | `endpoints/users.md` |
| Cross-sample executions search, or single-execution detail / polling a run (`/executions/search`, `/executions/<id>`) | `endpoints/executions.md` |
| Data file detail / contents / cross-sample search, data-type discovery, **or uploading a generic data file** (`/data/<id>`, `/data/<id>/contents`, `/data/search`, `/data/types`, `POST /upload`) | `endpoints/data.md` |
| Downloading the bytes of a file (`/downloads/<data_id>/<filename>`) | `endpoints/downloads.md` |
| End-to-end recipes that chain endpoints | `examples.md` |

Cross-cutting rules (sections 6–8 below) apply to every endpoint and stay
inline.

## 6. Reliable querying patterns

1. Issue every read with the resolved runner's `flowbio api get … --json`
   (section 3), and use the same runner for the whole session.
2. For paginated endpoints, set `count` explicitly — never rely on the
   implicit default of 10. Cap at 100; the API rejects >100 with HTTP 400
   (not silent clamp).
3. Pass every user-supplied filter as `--param KEY=VALUE` (e.g.
   `--param name=rna-seq`); the CLI URL-encodes the value. Never interpolate
   user input into the path, and never put a `?` there.
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
     `/samples/search?<identifier>=<value>`. For a controlled-vocabulary
     attribute (`has_options=true`), also call
     `GET /samples/metadata/<identifier>/options` to discover the legal
     values before filtering, rather than guessing the value.

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
- Always pipe through `jq`; never paste raw CLI output verbatim into the
  user's view if it's longer than ~20 lines.
- If iterating across pages, accumulate results internally and report the
  rolled-up summary, not each page's raw envelope.
- Sample-metadata questions have a specific pitfall (list view vs detail
  view) — Read `endpoints/samples.md` before answering any "what
  metadata does sample X have?" question.

## 8. Error handling

Because every read passes `--json`, a failed `api get` writes a machine-readable
envelope to **stderr** — `{"message": …, "status_code": …}` — and exits
non-zero. Trust the server's **`status_code` and readable `message`** as the
primary signal: they are precise and come straight from Flow. The process
**exit code is a coarse secondary** signal (`0` ok, `2` usage, `3` auth, `4`
not found, `5` bad request) — use it only to corroborate, and always report the
server `message` verbatim.

Map the server `status_code` to a cause:

| `status_code` | Meaning | What to do |
|---|---|---|
| 400 | Wrong filter, wrong type, malformed value, or `count > 100` | Report the message verbatim. Suggest the closest valid filter from the relevant `endpoints/*.md`. For count, lower it. |
| 401 / 403 | Auth missing, expired, or insufficient | Report it, then give the authentication guidance in section 3 (how to create and save an API key). Do not silently retry anonymously. |
| 404 | Wrong path or non-public ID | Verify path against `endpoints/*.md`. If filtering by ID, fall back to discovery via the list endpoint. |
| 500 | Likely a non-integer `page`/`count` value (the API doesn't catch ValueError) | Confirm both are integers. If they are, report as a server-side issue and stop. |
| 5xx (other) | Server-side | Report once. Do not retry — the user retries manually. |

Two more cases have **no** error — the read succeeds (exit `0`) but the body
needs interpreting:

| Result | Meaning | What to do |
|---|---|---|
| Empty list | No resources visible to this caller match | Not a failure. Tell the user "no matches found". If the read was unauthenticated, remind them many resources on Flow are private and an authenticated caller may see more (section 3). |
| Result count unchanged after adding a filter | Filter likely silently ignored — unknown identifier on this instance | Confirm the identifier exists via `GET /samples/metadata` (or the relevant discovery endpoint). The API does not currently reject unknown filter params. |

A missing runner is not an API error — handle it via the preflight message in
section 4.1. For a network failure (DNS, timeout) the CLI exits non-zero with a
transport error and no `status_code`; report `FLOW_API_URL` and the failure,
and ask whether the URL is reachable.

Never silently swallow an error. If the CLI exits non-zero, report the server
`message` (or the transport error) and stop — do not fabricate a result.

## 9. Future shape

- **Bulk multi-file downloads:** the `POST /downloads/...` →
  `GET /downloads/<job_id>` zip flow is auth-gated and tracked separately.
- **When a machine-readable OpenAPI spec is available:** the per-endpoint
  files collapse to a single line — "fetch `<base>/openapi.json` and use
  it." Reliability tactics, output discipline, and error handling stay;
  they're operational, not endpoint-specific.
