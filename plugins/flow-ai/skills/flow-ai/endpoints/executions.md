# Executions search

Cross-sample executions search. Distinct from `/samples/<id>/executions`
(which scopes to a single sample). Use this when the user asks about
executions broadly ("which executions failed last week?",
"executions of pipeline X").

## `GET /executions/search`

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

## Cross-link

For executions associated with a *specific* sample, use
`/samples/<id>/executions` (see `endpoints/samples.md`). The
cross-sample search lives here.
