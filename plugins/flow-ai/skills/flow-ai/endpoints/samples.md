# Samples — search & detail

Covers:

- `GET /samples/search` — list / filter
- `GET /samples/<id>` — single-sample detail (full metadata bag, inlined raw filesets)
- `GET /samples/<id>/executions` — executions a sample appears in
- `GET /samples/<id>/data` — **every** data file related to the sample

Related files:

- Metadata attributes, controlled-vocabulary options, sample types, and
  editing a sample -> `GET /v2/reference/samples` (see "Finding out about the
  API" in `SKILL.md`)
- Uploading samples / multiplexed reads / annotation templates ->
  `endpoints/samples-upload.md`

## Visibility rules across the family — they disagree

The two visibility rules across the sample resource family **differ**:

- `/samples/search` and `/samples/<id>`: anonymous callers reach iff
  `sample.private == False` **OR** `sample.project.private == False`.
  A private sample inside a public project IS reachable.
- `/samples/<id>/executions` and `/samples/<id>/data`: anonymous callers
  reach iff `sample.private == False`. A private sample inside a public
  project — listed by `/samples/search` — returns **404** here.

With authentication, both rules broaden: detail and sub-resource calls
return any sample / executions / data the caller has access to via
ownership, project access, or sharing. The disagreement between the two
rules persists — it's about how anonymous visibility is computed — but
authenticated callers usually see both layers populated.

Flag this if the user is surprised when the detail endpoint returns a
record but the sub-resource 404s.

## Sample-metadata pitfall — three-part rule, in this order

1. **`/samples/search` returns an almost-empty `metadata` object by default.**
   The list view only includes attributes flagged `in_table=True`, which on many
   instances is none of them. An empty `metadata` from the list view does NOT
   mean the sample has no metadata.
2. **For metadata across *many* samples, add `full_metadata=true` to
   `/samples/search`.** Each item's `metadata` then carries every attribute the
   sample has, in the same shape as the detail endpoint. This is the only way to
   read metadata in bulk — it is what you want for "how many distinct values of
   X", "which samples have Y", or any cross-sample aggregation. Fetching
   `/samples/<id>` once per sample instead is 100x the calls and will time out on
   a real dataset.
3. **For metadata on *one* named sample, prefer `GET /samples/<id>`.** The detail
   endpoint returns the full metadata bag with richer per-attribute fields
   (`attribute_description`, `is_list`, `url_pattern`).

Whichever view you use, keep `.metadata` in your `jq` projection. The
list-summary worked example intentionally drops it; reusing that projection on a
metadata question makes you report "no metadata" even when the response contains
some.

## `GET /samples/search`

The audience-agnostic samples list. Returns public samples always; with
authentication, also returns the caller's owned and shared samples.

- **Auth:** none required. Authenticated callers receive a broader
  result set automatically (no URL change).
- **Visibility rule (anonymous):** `sample.private == False` OR its
  project is `private == False`. A private sample inside a public
  project **is** listed.
- **Visibility rule (authenticated):** the union of public samples,
  samples owned by the caller, samples in projects the caller can
  access, and samples shared with the caller.
- **Query params:**

| Name           | Type | Default    | Behaviour |
|----------------|------|------------|-----------|
| `page`         | int  | `1`        | Paginator page. Non-integer → HTTP 400 naming the field. |
| `count`        | int  | `10`       | Page size. Max 100; >100 → HTTP 400 (not silently clamped). |
| `sort`          | str  | `-created` | Supported values: `-created` (newest first), `name`, `-name`. Use only these; another value may fail with an error. |
| `owned`         | str  | (none)     | When set to `1`, `true`, or `yes`, restrict to samples owned by the authenticated caller. **Auth required AND must be verified first.** On this search endpoint a missing or invalid token is silently treated as anonymous (no 401), and `?owned=true` then silently filters to `owner=NULL` samples — returning a plausible but wrong number. `/me`, by contrast, returns 401 for a bad token, so gate on it: call `GET /me` first and require a successful response with a non-null `id` before trusting any `?owned=true` result. If `/me` returns 401 (exit 3), the caller is effectively anonymous — tell the user their token is missing or expired and how to authenticate. |
| `name`          | str  | (none)     | Case-insensitive substring match on sample name only. |
| `organism`      | str  | (none)     | Organism pk for exact match; or `true`/`yes`/`1` to filter to samples that have any organism; `false`/`no`/`0` to filter to samples with no organism. |
| `sample_types`  | str  | (none)     | Comma-separated sample-type **identifiers**. Match if the sample's type identifier is in the list. |
| `owner`         | str  | (none)     | Case-insensitive substring match on owner name, username, group-owner name, or group-owner slug. |
| `project`       | str  | (none)     | Case-insensitive substring match on project name. |
| `created_gt`    | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); sample created on or after this value (`__gte`). Passing an ISO-8601 string → HTTP 400 naming the field. |
| `created_lt`    | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); sample created on or before this value (`__lte`). Passing an ISO-8601 string → HTTP 400 naming the field. |
| `full_metadata` | str  | (none)     | When set to `1`, `true`, or `yes`, each item's `metadata` includes every attribute the sample has (richer shape, same as the detail endpoint), not just `in_table=True`. Off by default to keep list responses small. |
| `<metadata_id>` | str  | (none)     | Any metadata attribute identifier returned by `GET /v2/metadata-attributes` on this instance. Legal identifiers are **per-instance** — admins curate their own — so always discover at runtime; do not assume a specific identifier exists. Matches metadata values via case-insensitive substring. `true`/`yes`/`1` filters to samples that have any value for the attribute; `false`/`no`/`0` excludes them. |

- **No free-text `filter` parameter.** `/samples/search` does not accept
  a single cross-field substring. To search "any field for the word X", the agent
  must pick a specific field (usually `name`) or issue separate calls.
  When a user gives a vague natural-language query ("the human
  samples"), prefer `organism` over `name` — `organism` is exact, `name`
  is a substring that often over-matches.

- **Silent no-op on unknown filter params.** The API silently
  ignores query params it doesn't recognise — including metadata
  identifiers that don't exist on this instance. A request like
  `?tissue=brain` on an instance with no `tissue` attribute returns
  the **unfiltered** result set with no error and no warning.

  **Detection:** call `GET /v2/metadata-attributes` first to confirm an
  identifier exists on this instance before issuing a filter against
  it. If you must skip the check, compare the result count to the
  same query without your candidate filter — if they match, the
  filter was ignored.

- **Value discovery depends on the attribute kind.** `GET /v2/metadata-attributes`
  lists the legal *identifiers*; to learn the *values* an attribute takes:
  - **Controlled-vocabulary attributes (`has_options=true`)** — call
    `GET /v2/metadata-attributes/<identifier>/options` (its reference is
    `/v2/reference/samples`) for the legal value set, then filter `/samples/search?<identifier>=<value>` with an
    exact option value. This is the precise path.
  - **Free-text attributes (`has_options=false`)** — there are no options;
    values may follow instance-specific conventions that substring search alone
    cannot reliably target — e.g. `?source=brain` may miss samples whose
    `source` is `"Temporal Cortex"` or `"Hippocampus"`. **Workaround:** fetch a
    small sample of records via `/samples/search?count=10` and inspect their
    `metadata.<id>.value` fields to learn the value vocabulary, *then* construct
    a substring filter.

- **Response envelope:** `{"count": int, "page": int, "samples": [...]}`.
  Envelope `count` is the **total matching samples across all pages**,
  not the page size. The word `count` therefore means "page size" in the
  request and "total matches" in the response.
- **Per-item fields:**
  - `id` (str — stringified pk)
  - `name` (str)
  - `created` (**int — Unix timestamp**, same shape as the detail endpoint)
  - `can_delete` (bool — `false` for unauthenticated callers; may be
    `true` for authenticated callers who own the sample)
  - `organism` — `{"id": str, "name": str}` or `null`
  - `sample_type` — `{"identifier": str, "name": str}` or `null`
  - `metadata` — object keyed by attribute identifier; values are
    `{attribute_name, value, annotation}`. **Only attributes flagged
    `in_table=True` appear here.** An empty `metadata` object means
    "no in-table-flagged metadata" — the sample may still have other
    metadata in Flow that this endpoint does not expose. When answering
    questions about a sample's metadata, phrase it as "the search
    endpoint exposes these fields" rather than "the sample has no
    metadata".
  - `project_name` (str|null)
  - `owner_name` (str|null — owner's display name, falling back to
    group owner; `null` if the sample has neither)
  - `is_paired` (bool — `true` if any of the sample's filesets contains
    more than one read file, i.e. paired-end sequencing data)

## `GET /samples/<id>`

Single-sample detail. Use this when the user asks about a specific
sample by id (or by name → list endpoint to discover the id, then this
endpoint to read the full record). The response is a richer projection
than `/samples/search`'s list item — most importantly, it carries the
**full** metadata bag rather than the in-table-flagged subset.

- **Auth:** public, no auth required.
- **Visibility rule:** see "Visibility rules across the family" above —
  same loose rule as `/samples/search`, **looser** than the
  `/executions` and `/data` sub-resources.
- **Query params:** **none**.
- **Response shape:** a **single object** (no envelope, no array).
- **Top-level fields:**
  - `id` (str — stringified pk)
  - `created` (**int — Unix timestamp**, NOT ISO-8601). Same shape as
    `/samples/search`'s `created` field.
  - `name` (str)
  - `private` (bool — `false` if a public parent project forces it
    public, otherwise the sample's own flag)
  - `can_edit` (bool — **always `false`** for anonymous callers; ignore)
  - `pubmed` (str — PubMed id, may be `""`)
  - `sample_type` (**str** — the sample type's `name`, or `""`).
    Plain string here; on `/samples/search` the same field is the
    object `{identifier, name}`. **Discrepancy.**
  - `metadata` — object keyed by attribute identifier. **This is the
    full metadata bag — every attribute the sample has, not just
    `in_table=True`.** Each value is a richer shape than the list
    endpoint's:
    ```
    {
      "attribute_name": str,
      "attribute_description": str,
      "is_list": bool,
      "url_pattern": str,
      "value": str | null,
      "annotation": str | null
    }
    ```
    Use this endpoint, not `/samples/search`, when the user asks
    about a sample's metadata.
  - `organism` — `{id: str, name: str}` or `null`
  - `filesets` — array of `{id, created, data: [{id, filename, size}]}`,
    where each fileset's `data` is filtered to `is_removed=False`,
    `is_ready=True`. **This is the raw input files only** — the
    sample's own filesets, not pipeline-produced outputs. To list
    every file related to the sample (raw inputs *plus* pipeline
    outputs), use `/samples/<id>/data`. See the "raw input files vs
    sample-related data" trap above. Each `data.id` here is consumable
    by the `data` and `downloads` endpoints directly.
  - `owner` — `{username, name, image}` or `null`
  - `group_owner` — `{slug, name}` or `null`
  - `project` — `{id, name}` or `null`
- **Cross-link to the list view.** `/samples/search` finds samples by
  filter; this endpoint reads the full record for one. The two together
  cover discovery + drill-down.

## `GET /samples/<id>/executions`

- **Auth:** public, but **stricter than `/samples/search`** — see
  "Visibility rules" above.
- **Query params:**

| Name     | Type | Default | Behaviour |
|----------|------|---------|-----------|
| `page`   | int  | `1`     | Paginator page. Non-integer → HTTP 400 naming the field. |
| `count`  | int  | `10`    | Page size. Max 100; >100 → HTTP 400. |
| `filter` | str  | (none)  | Single case-insensitive substring; spans multiple fields. |

- **Filter scope:** substring matched against any of `identifier`,
  `pipeline_version.pipeline.name`, `pipeline_version.name`, `fileset.name`,
  `fileset.organism.name`, `sample.name`, `owner.name`, `group_owner.name`.
  **Status shortcut footgun:** the view checks
  `query.lower() in "completed"/"error"/"canceled"`, so very short filters
  (`c`, `co`, `e`, `er`, `ca`) over-match status. Prefer filters of 3+ chars.
- **Sort:** fixed at `-created`.
- **Response envelope:** `{"count": int, "page": int, "executions": [...]}`.
  `count` is the total matching executions across all pages.
- **Per-item fields:**
  - `id` (str — stringified pk)
  - `identifier` (str)
  - `pipeline_name` (str)
  - `pipeline_version` (str)
  - `created`, `started`, `finished` (ISO-8601 strings; `started`/`finished`
    may be `null` until set)
  - `status` (str — e.g. `"OK"`, `"CANCELED"`; the full enum is not
    documented here)
  - `sample_name` (str|null)
  - `fileset` — `{id, name, organism: {id, name}|null}` or `null`
  - `retries` — `{id, identifier}` or `null` (the execution this is a retry OF)
  - `retried_by` — `{id, identifier}` or `null` (the execution that retried this)
  - `owner_name` (str)
  - `can_delete` (bool — **always `false`** for anonymous callers; ignore)
- **Fields NOT exposed here** (without auth): `command`, logs, cost,
  parameters, process executions, `nextflow_id`, `output_data`. Public
  callers see the table-row summary only. For an execution's command, logs
  or outputs, follow its `id` to `GET /executions/<id>` (see
  `endpoints/executions.md`).

## `GET /samples/<id>/data`

Returns **every** Data row associated with the sample — raw input
files **plus** every pipeline-produced output traced back to it. This
is the union described in "raw input files vs sample-related data"
above. Prefer this over `/samples/<id>` for any "list / show / count
the files for sample X" question that isn't explicitly scoped to raw
inputs.

- **Auth:** public; same strict rule as `/executions` — anonymous callers
  need `sample.private == False`. Private sample inside a public project → 404.
- **Query params:** identical table to `/executions` (`page`, `count`, `filter`).
- **Filter scope:** substring matched against any of `filename`,
  `upstream_process_execution.process_name`,
  `upstream_process_execution.execution.pipeline_version.pipeline.name`,
  `upstream_process_execution.execution.sample.name`,
  `upstream_process_execution.sample.name`, `fileset.sample.name`,
  `owner.name`, `group_owner.name`.
- **Sort:** fixed at `-created`.
- **Response envelope:** `{"count": int, "page": int, "data": [...]}`. Note
  the array key is `data`, not `samples`/`executions`.
- **Per-item fields:**
  - `id` (str — **this is the Data id consumed by the `data` and
    `downloads` endpoints**)
  - `filename` (str — base name; this exact value is the URL segment for
    direct download)
  - `size` (int — bytes)
  - `absolute_path` (str — Flow-internal server-side path; do not surface
    this to the user, it is not a useful identifier outside Flow)
  - `created` (ISO-8601 string)
  - `pipeline_name` (str|null — pipeline that produced the data, if any)
  - `process_execution_name` (str|null)
  - `sample_name` (str|null)
  - `owner_name` (str)
  - `can_delete` (bool — **always `false`** for anonymous callers; ignore)
- **Chaining.** Each `id` from this endpoint can be passed straight to:
  - `GET /v2/data/<id>` for the full data record (see `GET /v2/reference/data`),
  - `GET /data/<id>/contents` for a text preview (see `endpoints/data.md`),
  - `GET /downloads/<id>/<filename>` for the file bytes (see `endpoints/downloads.md`).

## Raw input files vs sample-related data — the trap

A sample has TWO different "data" projections in the API and they are
NOT the same set:

- **Inlined `filesets` on `/samples/<id>`** is just the sample's own
  filesets — i.e. the raw input files that *make up* the sample (the
  uploaded FASTQs / BAMs / whatever). It does **not** include anything
  produced by running a pipeline on the sample.
- **`/samples/<id>/data`** is the union of:
  1. files produced by a pipeline run on this sample
  2. files produced by a step of any run that processed this sample, such
     as a run over several samples
  3. the sample's own raw input files (the same as its inlined `filesets`)

  So `/samples/<id>/data` = raw inputs **plus** every pipeline-output
  file traced back to the sample. For a sample that has been run
  through several pipelines this can be hundreds of files; the inlined
  filesets only show the small handful of raw inputs.

**How to choose:**

- "What raw files / FASTQs / inputs does sample X have?" → use
  `/samples/<id>` and read `filesets[].data`.
- "What files are *in* / *associated with* / *related to* sample X?",
  "list all the data for sample X", or any unqualified "files for
  sample X" → use `/samples/<id>/data`. The unqualified question
  almost always means the union, not just the raw inputs.
- If unsure, prefer `/samples/<id>/data` — it's the superset, and its
  per-row `pipeline_name` lets the user see at a glance which files
  are raw inputs (`pipeline_name == null`) and which came from a
  pipeline.

For samples that have never been processed, the two views converge to
the same set, which is why this trap is invisible until you hit a
real, processed sample.

