# Pipelines endpoint

## `GET /pipelines`

- **Auth:** public, no auth required.
- **Query params:** **none**. The view ignores `request.GET` entirely — no
  `page`, no `count`, no `filter`. Passing query params is silently a no-op.
- **Pagination:** **none**. The full catalog is returned in a single response
  as a **bare JSON array** (not the `{count, page, ...}` envelope used by the
  sample/project list endpoints).
- **Response shape.** Top-level array of category objects. Tree:
  - Category: `{name, description, subcategories: [...]}`
  - Subcategory: `{name, description, pipelines: [...]}`
  - Pipeline: `{id, name, description, execution_count, is_nfcore, prepares_genome}`
    - `id` — string (stringified integer pk).
    - `description` — taken from the most recent active version.
    - `execution_count` — total runs ever for this pipeline.
- **Per-pipeline version list is NOT exposed** on this endpoint. To get a
  pipeline's versions (e.g. to run it), follow up with `GET /pipelines/<id>`
  (below).
- **Implicit visibility filter (not user-controllable).** For unauthenticated
  callers, only pipelines with at least one active, non-private version
  appear. Empty subcategories and categories are dropped.

**With authentication:** the catalogue broadens to include pipelines
the caller can see via project access, ownership, or sharing. The URL
is unchanged. When the token file (see `SKILL.md` section 3) is
present, the agent must attach the `Authorization: Bearer …` header
on this call too — broadening is automatic from there.

## `GET /pipelines/<id>`

Single-pipeline detail. Use this after `/pipelines` to discover a pipeline's
**versions** — you run a *version*, not a pipeline (see "Running a pipeline"
below).

- **Auth:** public GET. Broadens with auth to include versions the caller can
  see via ownership/sharing. Attach the `Authorization` header when the token
  file is present.
- **404 cases:** the pipeline id does not exist, **or** the pipeline has no
  version readable to the caller (e.g. all versions private and the caller is
  not an admin). Fall back to `/pipelines` discovery if you guessed the id.
- **Query params:** none.
- **Response shape:** a single object:
  - `id` (str), `name` (str)
  - `is_nfcore` (bool), `prepares_genome` (bool)
  - `repo_url` (str), `repo_original_url` (str)
  - `versions` — array of `{id, name, nextflow_versions}`, **most recent
    first**. `nextflow_versions` is the list of Nextflow versions available on
    this instance (see the default rule below).
- **Default version.** When the user does not name a version, use
  `versions[0]` — the most recent. (There is no separate "default" flag; the
  most-recent active version is what the catalog description is drawn from.)

## `GET /pipelines/versions/<id>`

Single pipeline-**version** detail, including the run **schema**. This is the
source of truth for what parameters a run accepts. Fetch it before building a
run body.

- **Auth:** public GET. **404** if the version is inactive, or if it is private
  and the caller is not an admin.
- **Query params:** none.
- **Response shape:** a single object:
  - `id` (str), `name` (str), `long_description` (str)
  - `upstream_pipeline_versions` — versions whose output this one can consume.
  - `nextflow_versions` — array of available Nextflow version strings, sorted by
    version string descending (so `[0]` is the highest-sorting string — usually,
    but not guaranteed to be, the newest release).
  - `schema` (object) — the Flow pipeline schema. Its structure is documented
    at `docs.flow.bio/docs/admin/adding-pipelines` ("Schema Files"); the run
    mapping you need is summarised under "Running a pipeline" below.
- **Default Nextflow version.** The API does **not** expose which entry is the
  instance's configured default. When the user does not specify one, use
  `nextflow_versions[0]` (the first of the descending-sorted list). The run
  endpoint requires a value, so one must always be sent.

## Running a pipeline — `POST /pipelines/versions/<id>/run`

Kicks off an execution of a pipeline version. **This is a mutation** (it changes
remote state and consumes compute — runs often take hours), and it **always
requires the token**. Performed with a single `curl` POST of a JSON body — not
the flowbio CLI, which has no run command.

### Capability & auth

- The token is mandatory. With no token file present, do not attempt the run —
  tell the user a token is required.
- **403 `{"error": "User cannot run pipelines"}`** — the user's
  `can_run_pipelines` flag is false. Report verbatim; the user lacks run
  permission. Do not retry.
- **403 `{"error": "Token not authorised for this endpoint"}`** — the token's
  scope does not permit running. Report that the token isn't authorised to run
  pipelines and stop. Do not retry or try to escalate scope.

### The run flow (chain these calls)

1. `GET /pipelines` → match the user's name to a pipeline `id`.
2. `GET /pipelines/<id>` → choose the version `id` (the named one, else
   `versions[0]`).
3. `GET /pipelines/versions/<version_id>` → read `schema` and
   `nextflow_versions`.
4. Resolve parameters from the schema (see mapping below), gathering values from
   the user or from discovery; resolve any named samples/data/filesets to ids.
5. **Confirm** (see the confirmation gate below).
6. `POST /pipelines/versions/<version_id>/run` with the JSON body.
7. Report the execution id, identifier, status, and the UI link. Poll only if
   the user asked (see "After submitting").

### Request body

The view injects `pipeline_version`, `owner`, and `creator` itself. Send a JSON
object with these fields:

| Field | Type | Notes |
|---|---|---|
| `params` | object | `{cli_param: value}` for `string` / `number` / `boolean` / `hidden` params. Values are strings ("true"/"false" for booleans). |
| `data_params` | object | `{cli_param: data_id}` for `data` params. Each value is a readable Flow data id (string/int). |
| `csv_params` | object | `{cli_param: {rows: [...], mode?, paired?}}` for `csv` params (samplesheets). See the csv rules below. |
| `nextflow_version` | string | **Required.** Use `nextflow_versions[0]` unless the user named one. |
| `fileset` | int | Optional. A readable fileset id associated with the run. It does **not** auto-fill any section's data inputs — resolve those into `data_params` yourself (see autofill below). |
| `retries` | int | Optional. Id of a prior execution being retried; must be the **same** pipeline version. Use only for an explicit "retry/re-run" request. |
| `resequence_samples` | bool | Optional/advanced. Omit unless the user explicitly asks for it. |

**Always send `params`, `data_params`, and `csv_params`** — each as `{}` when
you have nothing for it. The form's validation indexes all three keys directly,
so omitting any one is an error (HTTP 500), not an empty default.
`nextflow_version` is likewise always required. The other fields (`fileset`,
`retries`, `resequence_samples`) are genuinely optional and may be omitted.

### Schema → body mapping (full parity)

Walk `schema.inputs[]` (sections); each has a `params` map whose **key** is the
command-line string (after `--`). A param may override the submitted key with
its own `param` field — use that when present. Sections may carry `advanced`
(hidden-by-default in the UI; still fill required params), `modes` (a toggle —
see below), and `from_fileset` / `from_execution` (autofill — see below).

For each param, bucket by `type`:

- **string / number** → `params[cli] = value`. Honour `default`; if the param
  has a `valid` list, the value must be one of those.
- **boolean** → `params[cli] = "true"` or `"false"`. If there is no `default`
  and the user does not set it, **omit** it (matches the UI: an untouched toggle
  is not sent).
- **hidden** → always send `params[cli] = default`.
- **data** → `data_params[cli] = <data_id>`. Resolve the id via discovery,
  honouring the param's filters: `pattern` (filename regex), `category`
  (1 generic, 2 annotation, 3 multiplexed, 4 demultiplexed), `data_types`. Find
  candidates with `GET /data/search`, `GET /samples/<id>/data`, etc. (see
  `endpoints/data.md`, `endpoints/samples.md`).
- **csv** → `csv_params[cli] = {rows: [...]}`. See below.

### csv params (samplesheets)

A `csv` param becomes `{rows: [...]}`, optionally with `mode` (when the param
has `modes`) and `paired` (`"both"` (default) / `"first"` / `"second"` — for
paired-end handling). Each row is `{sample?, fileset?, values: {col: val}}`:

- If the param has `takes_samples: true`, give **one row per sample**:
  `{sample: <sample_id>, values: {}}`. Resolve sample names to ids first
  (constrain to `sample_types` if set).
- If `takes_filesets: true`, give one row per fileset: `{fileset: <fileset_id>,
  values: {}}` (constrain by `fileset_category` / `fileset_size`).
- **You usually only need the sample/fileset id.** This is genuinely
  server-side, and is **not** the same as the section-level `from_fileset` /
  `from_execution` autofill below (which is UI-only). When the run actually
  executes, the backend builds the CSV file from the schema's `columns`
  (`Execution.prepare_csvs`, invoked from `Execution.run`): for each column it
  takes the row's `values[<column name>]` if you supplied one, otherwise it
  fills the column itself when it has a **column-level** `from_sample` (a sample
  attribute, a metadata identifier, or a file index into the sample's fileset)
  or a column-level `from_fileset` (a fileset attribute or file index). So put a
  value in `values` (keyed by the column's `name`) **only** for columns the
  server won't fill — a custom column, or a column with no `from_sample` /
  `from_fileset`. Note the server resolves `from_sample`/`from_fileset` but does
  **not** apply a column's `default` for you, so supply that explicitly if the
  pipeline needs it.

### Autofill: `from_fileset` / `from_execution` sections

`from_fileset` and `from_execution` are **UI render conveniences** — in the web
app the user picks a fileset/execution and the front end pre-fills that
section's `data` inputs. There is **no server-side autofill on the run
endpoint**: the API only ever receives concrete ids in `data_params` (and
`csv_params`). So the skill resolves the ids itself in both cases and places
them in `data_params`:

- **`from_fileset` section:** if the user names a fileset, read its data files
  (e.g. via `GET /data/search` scoped to that fileset, or the sample's
  `GET /samples/<id>/data`) and, for each `data` param in the section, pick the
  file matching the param's `fileset_pattern` (else its `pattern`). Put the
  chosen ids in `data_params`. (The top-level `fileset` body field does **not**
  do this for you.)
- **`from_execution` section:** read the chosen execution's outputs
  (`GET /executions/<id>`), match each data param's `execution_output.process` /
  `execution_output.pattern` against the process outputs, and put the resulting
  ids in `data_params`.

### Modes

When a section defines `modes`, pick one (ask the user, or use the obvious
single mode) and include only that mode's params, using each param's
mode-specific `param` name. For a `csv` param, set `mode` on the csv object so
the server selects the matching column schema.

### Confirmation gate

Running changes remote state and consumes compute. Before the POST, show the
user a summary and proceed **only on explicit confirmation**:

- pipeline name and the version (name + id),
- the resolved `params`, `data_params`, and `csv_params` (sample/fileset names,
  not just ids, where you resolved them),
- the Nextflow version,
- the owner it will run as (the token's user).

The read/discovery steps (steps 1–4) need no confirmation.

### The call

```bash
curl -s -A "flow-ai/0.7.0" \
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \
  -H "Content-Type: application/json" \
  -X POST \
  --data '{"params":{...},"data_params":{...},"csv_params":{...},"nextflow_version":"23.04.3"}' \
  "${FLOW_API_URL:-https://app.flow.bio/api}/pipelines/versions/<version_id>/run"
```

Every value in that body is something you resolved in steps 1–4 — there are no
constants. In particular `nextflow_version` is **your choice**: take it from the
version's `nextflow_versions` (default `nextflow_versions[0]`) unless the user
named a specific one. The `"23.04.3"` above is just an illustrative resolved
value, not a fixed string to send.

Preserve token discipline (SKILL.md §1): the token is referenced only via
`$(< ~/.config/flow/api-token)` inside the header — never `cat`/`echo`/printed.

### Success

Exit 0 with the full execution object (the same shape as
`GET /executions/<id>` — see `endpoints/executions.md`). Report:

- `id`, `identifier`, and the initial `status` (a fresh run's `status` is an
  empty string `""` or `-` — i.e. not yet terminal; see
  `endpoints/executions.md` for the status values),
- a **link to the run in the UI**, derived from the base URL by stripping a
  trailing `/api`:

  ```bash
  WEB="${FLOW_API_URL:-https://app.flow.bio/api}"; WEB="${WEB%/api}"
  echo "$WEB/executions/<id>/"
  ```

  e.g. `https://app.flow.bio/api` → `https://app.flow.bio/executions/<id>/`;
  `https://staging.flow.bio/api` → `https://staging.flow.bio/executions/<id>/`.

### After submitting — polling

**Do not poll by default.** Return the id and the UI link and stop. Poll only
when the user explicitly asks to be told when it finishes:

- Poll `GET /executions/<id>` on an interval of **at least 60 seconds** (runs
  commonly take hours — a slower cadence is fine; never busy-wait).
- Stop when `status` is terminal: `OK`, `ERROR`, or `CANCELED`.
- On `OK`, report success (optionally a short log tail). On `ERROR`, surface the
  execution's `stderr`/`log` — never claim success. See `endpoints/executions.md`
  for the detail fields and `?log=<offset>` tailing.

### Errors

| Status | Meaning | What to do |
|---|---|---|
| 400 | Form validation — bad/missing param, unknown/unreadable data/sample/fileset id, unknown Nextflow version | Body is `{"error": {field: [messages]}}`. Report the field message verbatim; fix the offending value (e.g. re-resolve the id, pick a valid Nextflow version) and re-confirm before resubmitting. |
| 403 | `User cannot run pipelines` **or** `Token not authorised for this endpoint` | Report verbatim and stop (see "Capability & auth"). Do not retry. |
| 404 | Version id unknown, inactive, or private-to-non-admin | Re-resolve the version via `GET /pipelines/<id>`. |

Never report a started execution on a non-2xx response.
