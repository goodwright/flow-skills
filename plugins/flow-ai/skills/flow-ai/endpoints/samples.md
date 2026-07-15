# Samples endpoints

Covers the eight sample-related endpoints:

- `GET /samples/search` — list / filter
- `GET /samples/<id>` — single-sample detail; inlines the sample's
  **raw input filesets only**
- `GET /samples/<id>/executions` — executions a sample appears in
- `GET /samples/<id>/data` — **every** data file related to the sample
  (raw inputs **plus** pipeline-produced outputs)
- `GET /samples/metadata` — metadata attribute schema for this instance (discovery)
- `GET /samples/metadata/<identifier>/options` — controlled value set for one
  attribute (value discovery)
- `GET /samples/types` — sample-type enum (discovery)
- `GET /samples/types/<identifier>` — single sample-type detail

## Raw input files vs sample-related data — the trap

A sample has TWO different "data" projections in the API and they are
NOT the same set:

- **Inlined `filesets` on `/samples/<id>`** is just the sample's own
  filesets — i.e. the raw input files that *make up* the sample (the
  uploaded FASTQs / BAMs / whatever). It does **not** include anything
  produced by running a pipeline on the sample. Implementation: this is
  `s.filesets` on the model.
- **`/samples/<id>/data`** is `Sample.data`, defined as the union of
  three querysets:
  1. `Data` whose upstream `process_execution.execution.sample` is this
     sample (pipeline outputs at execution scope)
  2. `Data` whose upstream `process_execution.sample` is this sample
     (pipeline outputs at process scope)
  3. `Data` whose `fileset.sample` is this sample (raw inputs — same as
     bucket 1 of the detail view)

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

## Sample-metadata pitfall — two-part rule, in this order

1. **Prefer `GET /samples/<id>` over `/samples/search` for sample-level
   metadata questions.** The detail endpoint returns the **full** metadata
   bag — every attribute the sample has, with richer per-attribute fields
   (`attribute_description`, `is_list`, `url_pattern`). The list endpoint
   only includes the `in_table=True` subset and uses a simpler value shape.
   An empty `metadata` from the list view does NOT mean the sample has no
   metadata; the detail endpoint is the source of truth.
2. **If you do read metadata from the list view, keep `.metadata` in your
   `jq` projection.** The list-summary worked example intentionally drops
   it; reusing that projection on a metadata question makes you report
   "no metadata" even when the response contains some. Project
   `{id, name, metadata}` (and re-run if you've already lost it). For
   "tell me about sample X" questions, jump straight to step 1 and avoid
   this trap entirely.

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
| `page`         | int  | `1`        | Paginator page. Non-integer raises 500. |
| `count`        | int  | `10`       | Page size. Max 100; >100 → HTTP 400 (not silently clamped). |
| `sort`          | str  | `-created` | Supported values: `-created` (newest first), `name`, `-name`. Other values are passed through to Django's `order_by` and may error if the field doesn't exist. |
| `owned`         | str  | (none)     | When set to `1`, `true`, or `yes`, restrict to samples owned by the authenticated caller. **Auth required AND must be verified first.** Two API quirks combine to make naive use dangerous: invalid/expired tokens are silently treated as anonymous (no 401), and `?owned=true` then silently filters to `owner=NULL` samples — returning a plausible but wrong number. Always call `GET /me` first and check that the response body's `id` field is non-null before trusting any `?owned=true` result. If `/me` returns nulls, the caller is effectively anonymous — tell the user their token is missing or expired. |
| `name`          | str  | (none)     | Substring match (`__icontains`) on sample name only. |
| `organism`      | str  | (none)     | Organism pk for exact match; or `true`/`yes`/`1` to filter to samples that have any organism; `false`/`no`/`0` to filter to samples with no organism. |
| `sample_types`  | str  | (none)     | Comma-separated sample-type **identifiers**. Match if the sample's type identifier is in the list. |
| `owner`         | str  | (none)     | Substring match (`__icontains`) on owner name, username, group-owner name, or group-owner slug. |
| `project`       | str  | (none)     | Substring match (`__icontains`) on project name. |
| `created_gt`    | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); sample created on or after this value (`__gte`). Passing an ISO-8601 string causes HTTP 500. |
| `created_lt`    | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); sample created on or before this value (`__lte`). Passing an ISO-8601 string causes HTTP 500. |
| `full_metadata` | str  | (none)     | When set to `1`, `true`, or `yes`, each item's `metadata` includes every attribute the sample has (richer shape, same as the detail endpoint), not just `in_table=True`. Off by default to keep list responses small. |
| `<metadata_id>` | str  | (none)     | Any metadata attribute identifier returned by `GET /samples/metadata` on this instance (see that section below). Legal identifiers are **per-instance** — admins curate their own — so always discover at runtime; do not assume a specific identifier exists. Matches metadata values via substring (`__icontains`). `true`/`yes`/`1` filters to samples that have any value for the attribute; `false`/`no`/`0` excludes them. |

- **No free-text `filter` parameter.** Unlike the now-deprecated list
  endpoint, `/samples/search` does not accept a single
  cross-field substring. To search "any field for the word X", the agent
  must pick a specific field (usually `name`) or issue separate calls.
  When a user gives a vague natural-language query ("the human
  samples"), prefer `organism` over `name` — `organism` is exact, `name`
  is a substring that often over-matches.

- **Silent no-op on unknown filter params.** The API silently
  ignores query params it doesn't recognise — including metadata
  identifiers that don't exist on this instance. A request like
  `?tissue=brain` on an instance with no `tissue` attribute returns
  the **unfiltered** result set with no error and no warning.

  **Detection:** call `GET /samples/metadata` first to confirm an
  identifier exists on this instance before issuing a filter against
  it. If you must skip the check, compare the result count to the
  same query without your candidate filter — if they match, the
  filter was ignored.

- **Value discovery depends on the attribute kind.** `GET /samples/metadata`
  lists the legal *identifiers*; to learn the *values* an attribute takes:
  - **Controlled-vocabulary attributes (`has_options=true`)** — call
    `GET /samples/metadata/<identifier>/options` (documented below) for the
    legal value set, then filter `/samples/search?<identifier>=<value>` with an
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
| `page`   | int  | `1`     | Paginator page. Non-integer raises 500. |
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
  callers see the table-row summary only. Decline questions about command
  text or execution outputs — they require authenticated endpoints that
  are out of scope here.

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
  - `GET /data/<id>` for the full data record (see `endpoints/data.md`),
  - `GET /data/<id>/contents` for a text preview (see `endpoints/data.md`),
  - `GET /downloads/<id>/<filename>` for the file bytes (see `endpoints/downloads.md`).

## `GET /samples/metadata`

Discovery endpoint for the metadata attributes defined on this Flow
instance. **This is the canonical "what filters can I use on
`/samples/search`?" endpoint.** Metadata attributes are user-defined
per-instance — admins of each Flow deployment curate their own set.
Hard-coded identifiers in skill docs would be wrong on most
instances, so always discover at runtime.

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array of `MetadataAttribute` rows,
  ordered by the admin-configured `order` field.
- **Per-item fields:**
  - `identifier` (str — the filter key on `/samples/search`; e.g.
    `"source"`, `"condition"`, `"experimental_method"` on instances where
    those exist)
  - `name` (str — human-readable label)
  - `description` (str — admin-supplied description)
  - `in_table` (bool — true if this attribute appears in the
    `/samples/search` list-view's `metadata` projection by default)
  - `has_options` (bool — true if the attribute has a controlled
    value set; false for free-text)
  - `all_sample_types` (bool — true if this attribute applies to all
    sample types; false if it is restricted to specific types listed
    in `sample_type_links`)
  - `regex_validator` (str|null — regex applied to values if set)
  - `required` (bool), `required_for_public` (bool), `is_list` (bool),
    `allow_user_terms` (bool), `allow_annotation` (bool),
    `url_pattern` (str|null), `order` (int)
  - `sample_count` (int — number of distinct samples that carry a
    value for this attribute)
  - `sample_type_links` (array — per-sample-type requirement overrides;
    empty when `all_sample_types=true` and no per-type rules exist.
    Each item: `{sample_type_identifier: str, sample_type_name: str,
    required: bool, required_for_public: bool}`)

**Key behaviour to surface to agents:**

- This is the source of truth for legal `?<identifier>=value`
  filters on `/samples/search`. Call this first when the user asks
  a metadata-scoped question — never guess at identifiers.
- Identifiers vary by instance. The skill never asserts that a
  specific identifier exists; it teaches discovery.
- `has_options=true` attributes have a controlled value set — filter
  values should come from that set. Call
  `GET /samples/metadata/<identifier>/options` (below) to list the legal
  values, then filter `/samples/search?<identifier>=<value>`.
- `has_options=false` attributes are free-text — they have no options,
  so the options endpoint returns an empty set for them. Substring matching
  on `/samples/search?<identifier>=<substring>` is the only filter
  mechanism. Values may follow instance-specific conventions
  (e.g. a `source` attribute holding `"Temporal Cortex"`,
  `"Hippocampus"`, etc.) — substring search alone may under-match
  if the user's natural-language term doesn't appear literally.

## `GET /samples/metadata/<identifier>/options`

Lists the controlled value set (the "options") for a single metadata
attribute. **This is the value-discovery counterpart to
`GET /samples/metadata`:** that endpoint tells you which attribute
*identifiers* exist; this one tells you the legal *values* for an
attribute whose `has_options` is `true`. Use it to turn a vague
natural-language value into an exact option before filtering
`/samples/search?<identifier>=<value>`.

- **Auth:** none required. Authentication broadens the result set: an
  authenticated caller additionally sees their **own** not-yet-validated
  options (terms they submitted that an admin hasn't validated). Anonymous
  callers — and authenticated callers, for everyone else's options — see the
  **validated** (admin-curated) set only. Pass `?validated=true` (below) when
  you want strictly the curated set regardless of who is calling.
- **Path param:** `<identifier>` — a metadata attribute `identifier` from
  `GET /samples/metadata`. Unknown identifier → **HTTP 404**
  `{"error": "Not found"}`. (An attribute with `has_options=false` exists but
  has no options, so it returns `200` with an empty `options` array and
  `count: 0` — not a 404.)
- **Query params:**

| Name        | Type | Default | Behaviour |
|-------------|------|---------|-----------|
| `validated` | str  | (none)  | When present, restricts by validation state. `validated=true` → only validated (admin-curated) options; **any other value** (e.g. `validated=false`) → only un-validated options within the caller's visible set (i.e. the caller's own pending terms). The check is literal `== "true"`. |
| `value`     | str  | (none)  | Case-insensitive substring (`__icontains`) on the option `value`. Use to narrow a large option set. |

- **No `page` param, and a hard cap of 100.** The `options` array contains at
  most the **first 100** options (ordered by `value` ascending). There is no
  pagination — if `count` exceeds 100, the extra options are **silently
  omitted**. Detect this by comparing `count` to the returned array length; when
  truncated, narrow with `?value=<substring>` rather than assuming you've seen
  every option.
- **Response envelope:** `{"count": int, "total_count": int, "options": [...]}`.
  - `total_count` — total options visible to the caller **before** the
    `validated`/`value` filters are applied.
  - `count` — total options matching **after** the `validated`/`value` filters.
    This is the cross-set total, **not** the page size, so it may exceed the
    100-item `options` length (see the cap above).
  - `options` — array (≤100) of `{id, value, validated}`.
- **Per-item fields:**
  - `id` (str — the option's pk; not usually needed for read-only filtering)
  - `value` (str — the legal value; pass this verbatim to
    `/samples/search?<identifier>=<value>`)
  - `validated` (bool — `true` for admin-curated options, `false` for
    un-validated user-submitted terms)
- **How to use it (discovery → filter):**
  1. `GET /samples/metadata` → find the attribute and confirm `has_options=true`.
  2. `GET /samples/metadata/<identifier>/options` → read the legal `value`s
     (optionally `?value=<substring>` to find the match for the user's term).
  3. `GET /samples/search?<identifier>=<value>` with an exact option value.
     Search matches metadata by substring, so an exact option value filters
     precisely without the under-match risk that free-text attributes carry.

This endpoint only exposes the read-only listing. Creating, merging,
editing, or deleting options are admin operations and are out of scope for
this skill (see SKILL.md section 1).

## `GET /samples/types`

Discovery endpoint for the sample-type enum on this instance. Used
to resolve a user-named sample type (e.g. "RNA-seq") to its
identifier for the `?sample_types=<identifiers>` filter on
`/samples/search`.

Small, finite list per instance (6 types on app.flow.bio today).

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array, ordered by name.
- **Per-item fields:**
  - `identifier` (str — the filter key, e.g. `"RNA-Seq"`,
    `"ChIP-Seq"`; pass to `?sample_types=` on `/samples/search`)
  - `name` (str — human label; often the same as `identifier`)
  - `description` (str — admin-supplied description)
  - `sample_count` (int — number of samples of this type)
  - `attributes` (array — the subset of metadata attributes that
    (1) have controlled options defined AND (2) have at least one
    value recorded against a sample of this type. This is a dynamic
    intersection, not a static schema declaration — an attribute that
    applies to all sample types will appear here for every type that
    has samples using it. For the full attribute schema, call
    `GET /samples/metadata`.)

## `GET /samples/types/<identifier>`

Single sample-type detail.

- **Auth:** none required.
- **Path param:** `<identifier>` from the list view (NOT a numeric pk —
  identifiers are the canonical lookup key). Returns HTTP 404 if not found.
- **Response shape:** a single object with the same fields as the
  list-item: `identifier`, `name`, `description`, `sample_count`,
  `attributes`. No additional fields are added at the detail level.

## Discovery pattern for sample types

1. `GET /samples/types` → list available types.
2. Match the user's term against `name` (case-insensitive).
3. Pass the matched `identifier` to
   `/samples/search?sample_types=<identifier>` (comma-separated for
   multiple).

## `POST /upload/sample` — upload a demultiplexed sample

Uploads a single demultiplexed sample (single-end or paired-end reads plus
metadata). **This is not a `curl` call** — it runs through the flowbio CLI on
demand. Read **SKILL.md section 4** first: it owns the runner preflight
(`uv`/`uvx` → `pipx` → existing `flowbio` → stop with an install message), the
pinned version, token discipline, base-URL handling, and the JSON / exit-code
contract. This section covers only what is specific to the sample call.

- **Inputs / flags:**
  - `--name NAME` (required) — the sample name. Must contain no spaces (the
    server rejects them).
  - `--sample-type IDENTIFIER` (required) — a sample-type **identifier**.
    Discover and resolve it via `GET /samples/types` (above) — match the user's
    term to a `name`/`identifier` and send the `identifier`. Sent as-is and
    validated **server-side**.
  - `--reads1 PATH` (required) — the (first) reads file. A single-end sample
    has only `--reads1`. A generic / non-sequencing file uploaded as a sample
    also goes here.
  - `--reads2 PATH` (optional) — the second reads file; supplying it makes the
    sample **paired-end**. Only valid alongside `--reads1`.
  - `--project ID` (optional) — a project **id** to assign the sample to.
    Resolve a project name → id via `GET /projects/search` (must be a project
    the user owns).
  - `--organism ID` (optional) — an organism **id**. Resolve a name / latin
    name → id via `GET /organisms`.
  - `--metadata KEY=VALUE` (optional, repeatable) — one metadata attribute per
    flag. Keys are attribute `identifier`s from `GET /samples/metadata`.

- **Discovery + local pre-flight (before running the CLI)** — reuse the
  existing read endpoints; **discover before uploading, never guess**:
  - **Sample type** — `GET /samples/types`; resolve the user's term to an
    `identifier`. Surface ambiguous matches to the user instead of guessing.
  - **Required metadata** — `GET /samples/metadata`. An attribute is required
    for the chosen sample type if its global `required` is `true` **OR** a
    `sample_type_links` entry whose `sample_type_identifier` matches the chosen
    type has `required: true`. Confirm the user supplied every such attribute
    **before** uploading; if any is missing, name it (by `identifier`/`name`)
    and stop. For `has_options` / `regex_validator` attributes, validate what
    you can locally, but the **server is the final authority** — the skill
    cannot enumerate an attribute's legal option values today (see the
    `GET /samples/metadata` notes above).
  - **Organism** — `GET /organisms`; resolve name / latin name → `id`.
  - **Project** — `GET /projects/search`; resolve name → `id`.
  - **Files & names** — confirm `reads1` (and `reads2` if given) exist, and
    that the reads filenames and the sample `name` contain **no spaces**. Tell
    the user to rename rather than attempting the upload.

- **Confirmation:** show the user the reads file(s) and whether the sample is
  single- or paired-end, the sample `name`, the resolved sample type, the
  project and organism (if given), and the metadata key/values — and upload
  **only on explicit confirmation** (SKILL.md §4.4).

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from "flowbio==0.9.0" flowbio samples upload \
    --name NAME --sample-type IDENTIFIER \
    --reads1 PATH [--reads2 PATH] \
    [--project ID] [--organism ID] [--metadata KEY=VALUE ...] \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"id": "<sample_id>"}`. Report the `sample_id`
  and that the sample is uploaded. (The JSON key is `id`, not `sample_id`.)

- **Errors:** a non-zero exit code carries the cause and the server message
  arrives on stderr — see **SKILL.md §4.3** for the exit-code table and the
  JSON error shape. The sample-specific causes to recognise:
  - **Bad request / validation** (exit `5`) — an invalid `sample_type`, missing
    required metadata, a value that fails an attribute's `options`/regex, spaces
    in the sample name or a filename, or an ownership rejection on the project.
    Report the server field message verbatim.
  - **Auth** (exit `3`) — the token is missing or expired;
    `~/.config/flow/api-token` is absent or stale.
  - **Usage** (exit `2`) — e.g. a local reads file was not found.
  Never report success on a non-zero exit.

## `GET /annotation/<sample_type>` — download an annotation-sheet template

Downloads the server-generated annotation sheet (`.xlsx`) for a sample type, to
fill in before a multiplexed upload (`POST /upload/multiplexed`, below). This is
a **read** helper — it changes no remote state, so it needs **no** confirmation
gate — but it still runs through the flowbio CLI (not `curl`) so auth and
base-URL handling stay uniform with the uploads. Read **SKILL.md section 4**
first for the runner preflight, token discipline, and the JSON / exit-code
contract.

- **Inputs / flags:**
  - `--sample-type IDENTIFIER` (optional, default `generic`) — a sample-type
    **identifier**. A type-specific template (e.g. `rna_seq`) includes columns
    for that type's metadata attributes; `generic` includes only the base
    columns common to all types. Resolve a user's natural-language type via
    `GET /samples/types` (above) and send the `identifier`. Sent as-is and
    validated **server-side**.
  - `-o PATH` / `--output PATH` (required) — the file to write the `.xlsx`
    workbook to (the template is binary).

- **Discovery (before running the CLI):** if the user named a sample type,
  resolve it to an `identifier` via `GET /samples/types`; surface ambiguous
  matches instead of guessing. If they gave none, use `generic`.

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from "flowbio==0.9.0" flowbio samples annotation-template \
    --sample-type IDENTIFIER -o ./template.xlsx \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"output": "<path>", "sample_type": "<id>"}`.
  Report where the template was written and that the user should fill in one row
  per sample (names, file paths, metadata) before running the multiplexed
  upload. There is **no** `id` key.

- **Errors:** a non-zero exit carries the cause and any server message on stderr
  (see **SKILL.md §4.3**). The template-specific causes:
  - **Not found** (exit `4`) — the sample type does not exist; re-resolve via
    `GET /samples/types`.
  - **Auth** (exit `3`) — the token is missing or expired.
  - **Usage** (exit `2`) — e.g. the output path is not writable.
  Never report success on a non-zero exit.

## `POST /upload/multiplexed` — upload multiplexed reads + an annotation sheet

Uploads one or two multiplexed reads files plus a completed annotation sheet for
server-side demultiplexing. **This is not a `curl` call** — it runs through the
flowbio CLI on demand. Read **SKILL.md section 4** first: it owns the runner
preflight, the pinned version, token discipline, base-URL handling, and the JSON
/ exit-code contract. This section covers only what is specific to the
multiplexed call.

**Annotation-first.** The library uploads and validates the **annotation sheet
before the reads**, so an invalid sheet never wastes a (large) reads upload.
Surface this in your messaging: if validation fails, no reads were uploaded.

- **Inputs / flags:**
  - `--reads1 PATH` (required) — the (first) multiplexed reads file. A
    single-end upload has only `--reads1`.
  - `--reads2 PATH` (optional) — the second reads file; supplying it makes the
    upload **paired-end**. Only valid alongside `--reads1`.
  - `--annotation PATH` (required) — the completed annotation sheet
    (`.xlsx` or `.csv`). Obtain a template via `samples annotation-template`
    (above).
  - `--reject-warnings` (optional flag) — by **default** annotation warnings are
    auto-accepted (the upload proceeds and the warnings are returned for
    display). Pass `--reject-warnings` only when the user wants warnings treated
    as **fatal** — the upload then fails on any warning so they can fix the
    sheet first.

- **Discovery + local pre-flight (before running the CLI):**
  - To help the user build the sheet, offer `samples annotation-template`
    (above) for the relevant sample type.
  - **Files & names** — confirm `reads1` (and `reads2` if given) and the
    annotation sheet exist, and that the filenames contain **no spaces**. Tell
    the user to rename rather than attempting the upload.

- **Confirmation:** show the user the reads file(s) and whether the upload is
  single- or paired-end, the annotation-sheet path, and whether warnings are
  auto-accepted (default) or rejected — and upload **only on explicit
  confirmation** (SKILL.md §4.4).

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from "flowbio==0.9.0" flowbio samples upload-multiplexed \
    --reads1 PATH [--reads2 PATH] \
    --annotation PATH [--reject-warnings] \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout
  `{"data_ids": ["<id>", …], "annotation_id": "<id>", "warnings": [...]}`.
  Report the `data_ids`, the `annotation_id`, and any `warnings` (show them so
  the user knows what was auto-accepted). This shape has **no** `id` key — do
  not look for one.

- **Errors:** a non-zero exit code carries the cause and the server message
  arrives on stderr — see **SKILL.md §4.3** for the exit-code table and the
  JSON error shape. The multiplexed-specific causes to recognise:
  - **Annotation validation** (exit `5`, bad request) — the sheet has hard
    validation errors, or it has warnings and the user chose `--reject-warnings`.
    The error JSON carries an `errors` array of per-row/field issues
    (`{"row": …, "message": …}`); show them. **No reads were uploaded**
    (annotation-first), so tell the user to fix the sheet and retry; if the
    failure was warnings-only, offer to retry **without** `--reject-warnings` to
    accept them.
  - **Auth** (exit `3`) — the token is missing or expired.
  - **Usage** (exit `2`) — e.g. a local reads or annotation file was not found,
    or an invalid reads-key combination.
  Never report success on a non-zero exit.
