# Executions

Covers:

- `GET /executions/search` — cross-sample executions search.
- `GET /executions/<id>` — single-execution detail, used to **poll a run** you
  started via `POST /pipelines/versions/<id>/run` (see `endpoints/pipelines.md`).

## `GET /executions/search`

Cross-sample executions search. Distinct from `/samples/<id>/executions`
(which scopes to a single sample). Use this when the user asks about
executions broadly ("which executions failed last week?",
"executions of pipeline X").

- **Auth:** none required for public executions; authenticated callers
  see executions on resources they have access to.
- **Visibility rule (anonymous):** an execution is visible if any of
  these three conditions holds:
  1. The execution's own `private` flag is `False`.
  2. It is a "dependent" execution (`dependent=True`) on a sample whose
     own `private` flag is `False` (i.e. the sample is publicly
     reachable).
  3. It is a "dependent" execution (`dependent=True`) on a project (via
     `execution.sample.project` or `execution.project`) whose `private`
     flag is `False`.
  The `dependent` flag distinguishes executions that ran as part of a
  sample's or project's analysis — visible alongside the parent — from
  standalone executions, which are only visible if their own flag is
  public.
- **Visibility rule (authenticated):** the union of public executions,
  executions the caller owns, and executions on samples / projects
  the caller has access to.
- **Query params:**

| Name                | Type | Default    | Behaviour |
|---------------------|------|------------|-----------|
| `page`              | int  | `1`        | Paginator page. |
| `count`             | int  | `10`       | Page size. Max 100; >100 returns HTTP 400. |
| `sort`              | str  | `-created` | Supported: `-created` (default), `name`, `-name`. |
| `name`              | str  | (none)     | Substring across pipeline name, pipeline version name, organism name, and fileset name. |
| `owned`             | str  | (none)     | Truthy string (`"true"`, `"1"`, `"yes"`) restricts to caller's own executions. |
| `pipeline_versions` | str  | (none)     | Comma-separated pipeline-version pks. |
| `pipeline`          | str  | (none)     | Exact pipeline pk (integer as string). |
| `pipeline_version`  | str  | (none)     | Exact pipeline-version pk. |
| `organism`          | str  | (none)     | Organism id (e.g. `"Hs"`). |
| `status`            | str  | (none)     | Execution status string (e.g. `"OK"`, `"ERROR"`, `"CANCELED"`). |
| `owner`             | str  | (none)     | Substring on owner name, username, group name, or group slug. |
| `created_gt`        | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); created on or after (`__gte`). Passing an ISO-8601 string causes HTTP 500. |
| `created_lt`        | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); created on or before (`__lte`). Passing an ISO-8601 string causes HTTP 500. |
| `duration_gt`       | float| (none)     | Duration in seconds; `finished - started >= value`. Executions without `started` or `finished` are excluded. |
| `duration_lt`       | float| (none)     | Duration in seconds; `finished - started <= value`. Executions without `started` or `finished` are excluded. |
| `process_execution` | str  | (none)     | Substring on process execution name (i.e. a step within the pipeline). |
| `nextflow_version`  | str  | (none)     | Exact Nextflow version string. |
| `terminal`          | str  | (none)     | Substring search across `stdout` and `stderr` of executions. Useful for finding executions whose output contains a specific message or error text. |
| `return_data`       | str  | (none)     | Truthy string (`"true"`, `"1"`, `"yes"`). When set, adds a `downstream_data` key to each execution item (array of `{id, filename, filetype, process_execution_name}`). |
| `return_inputs`     | str  | (none)     | Truthy string (`"true"`, `"1"`, `"yes"`). When set, adds an `inputs` key to each execution item (array of `{id, filename, filetype}`). |

- **No free-text `filter` parameter.** Filtering is field-scoped.
- **Response envelope:** `{"count": int, "page": int, "executions": [...]}`.
  Envelope `count` is the total matching executions across all pages.
- **Per-item fields** (from live API and serializer):
  - `id` (str — stringified integer pk)
  - `identifier` (str — human-readable slug, e.g. `"small_meucci"`)
  - `pipeline_name` (str)
  - `pipeline_version` (str — version name, e.g. `"1.7"`)
  - `created` (int — Unix timestamp)
  - `started` (float | null — Unix timestamp)
  - `finished` (float | null — Unix timestamp)
  - `status` (str — e.g. `"OK"`, `"ERROR"`, `"CANCELED"`, `"RUNNING"`)
  - `can_delete` (bool — always false for unauthenticated callers)
  - `retries` (object | null — `{id, identifier}` of the retry execution)
  - `retried_by` (object | null — `{id, identifier}` of the execution that retried this one)
  - `fileset` (object | null — `{id, name, organism: {id, name} | null}`)
  - `sample_name` (str | null)
  - `owner_name` (str — owner's display name, or group name if group-owned)

## Discovery patterns

- "Executions of the rna-seq pipeline" — find the pipeline pk from
  `/pipelines`, then `/executions/search?pipeline=<pk>`.
- "Failed executions last week" — `/executions/search?status=ERROR&created_gt=1746403200` (Unix timestamp; 2026-05-05T00:00:00Z = 1746403200).
- "My executions" — `/executions/search?owned=true` (requires auth).
- "Long-running executions (>1 hour)" — `/executions/search?duration_gt=3600`.

## `GET /executions/<id>`

Single-execution detail. Two main uses: drilling into a specific execution found
via `/executions/search`, and **polling a run** started via
`POST /pipelines/versions/<id>/run` (see `endpoints/pipelines.md`).

- **Auth:** per-object. The execution is readable if it (or a parent sample /
  project) is public, or if the authenticated caller owns it / has access. The
  owner of a run they just started can always read it. Attach the
  `Authorization` header when the token file is present. **404** if the id is
  unknown or not readable to the caller.
- **Query params:**

| Name      | Type | Default | Behaviour |
|-----------|------|---------|-----------|
| `log`     | int  | `0`     | Log **byte offset** to start from — returns log text from that offset onward (for incremental tailing across polls). Non-integer → HTTP 400. |
| `include` | str  | (none)  | Repeatable. Restrict the response to only these top-level fields. |
| `exclude` | str  | (none)  | Repeatable. Drop these top-level fields. Using both `include` and `exclude` → HTTP 400. |

- **This payload is large.** It nests the full pipeline schema, process
  executions, upstream data/samples, and log/stdout/stderr text. When polling,
  trim it — e.g. `?include=status&include=identifier&include=finished` — and
  only pull `log`/`stderr` when you need to report progress or diagnose a
  failure.
- **Response shape:** a single object. The fields relevant to running/polling:
  - `id` (str), `identifier` (str — human-readable slug), `uuid` (str)
  - `status` (str) — **the field to poll.** Terminal values: `OK`, `ERROR`,
    `CANCELED`. While the run is pending/in-flight it is **not** one of those —
    typically an empty string `""` or `-`. (There is no `RUNNING` value at the
    execution level; per-step progress like `RUNNING`/`COMPLETED` lives on
    `process_executions[].status`.) Poll until `status` is one of the three
    terminal values.
  - `created` / `started` / `finished` (int | null — Unix timestamps;
    `finished` is set once terminal)
  - `nextflow_version` (str)
  - `stdout` / `stderr` (str) and `log` (str — text from the `log` offset)
  - `command` (str — the Nextflow command; shell text. Surface only if asked.)
  - `params` / `data_params` / `csv_params` (the submitted inputs, echoed back)
  - `pipeline_version` — nested under the key **`pipeline`**; includes the
    pipeline name, version `name`, and `schema`.
  - `sample`, `project`, `fileset`, `owner`, `group_owner` (objects | null)
  - `retries` / `retried_by` (`{id, identifier}` | null)
  - `process_executions` — per-step status; useful for pinpointing a failure.
- **Internal fields — do not surface:** `absolute_path` anywhere in nested data,
  and raw server-side paths. Report `command`/`stderr` only when the user asks
  or to explain a failure.

### Polling a run

Poll **only when the user asked** to be told when it finishes (the run flow
returns the id + UI link and stops otherwise — see `endpoints/pipelines.md`).

1. `GET /executions/<id>?include=status&include=finished` on an interval of
   **≥ 60 seconds** (runs commonly take hours; a slower cadence is fine — never
   busy-wait).
2. Stop when `status` is `OK`, `ERROR`, or `CANCELED`.
3. On `OK`, report success (optionally tail the log via `?log=<offset>`). On
   `ERROR`, fetch and surface `stderr` / `log` / failing `process_executions` —
   never report success on a non-`OK` terminal status.

## Cross-link

For executions associated with a *specific* sample, use
`/samples/<id>/executions` (see `endpoints/samples.md`). The
cross-sample search lives here.
