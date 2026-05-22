# Flow concepts (for AI skills)

How Flow's domain model appears through its REST API. AI skills under
`.claude/skills/` reference this document so concepts are defined in one
place. Scope grows as more endpoints are exposed to agents — see the
"Open questions" section for placeholders.

## Resource hierarchy

```
project ──< sample ──< fileset ──< data
pipeline ──< pipeline_version ──< execution
```

A project groups samples (e.g. one experiment, one paper). A sample is a
biological sample with metadata; it owns one or more filesets, which are
collections of related files (e.g. paired-end FASTQs). Data are individual
files within a fileset.

A pipeline is a Nextflow workflow definition with one or more versions. A
pipeline version is the unit you actually run; an execution is a single
run of a pipeline version. Executions are exposed via `GET /executions/search`
and `GET /samples/<id>/executions` — see `endpoints/executions.md`.

## Identifiers

All resources use Django integer primary keys. There are no UUIDs and no
slugs in the public API. Identifiers are stable for the lifetime of the
resource. Note that ids are returned as **strings** in JSON (stringified
integers), not numbers.

To filter by something the user named ("the rna-seq pipeline", "human
samples"), the agent must first discover the ID by listing — no endpoint
accepts names directly as filter values. The pattern:

1. List the catalog endpoint with a coarse filter (or no filter).
2. Identify the right item by name in the response.
3. Use that item's ID as the filter value in the next call.

## Audience model

Flow resources have three audiences:

- **Public** — visible without authentication. Visibility rules are
  per-resource (see Samples and Projects below); they are stricter than
  a single `is_public` flag.
- **Owned** — owned by the calling user. Requires auth.
- **Shared** — shared with the calling user via Flow's permission system.
  Requires auth.

This skill targets a single audience-agnostic surface. Every endpoint it
uses returns the **union** of resources visible to the caller: public
resources always, plus owned and shared resources when a token is
attached. There is no "mode" — file presence (see SKILL.md section 3)
determines which audience the response covers.

"Public" is a strict subset, not a default. Most data on Flow is
private. An empty result from an unauthenticated request means
"nothing matches this query under the public visibility rule", not
"the API is broken". Authenticating typically returns more rows.

## Discovery endpoints

Flow exposes runtime discovery for the entities and attributes that
vary per instance: `GET /samples/metadata` (legal metadata attribute
identifiers), `GET /organisms` (organism enum), `GET /samples/types`
(sample-type enum), `GET /me` (authenticated identity),
`GET /users/search` (user directory).

When the user's question involves these concepts, the agent's first
move is the discovery endpoint, not the search endpoint:

- "human samples" → `/organisms` (resolve "human" to pk) → `/samples/search?organism=<pk>`
- "rna-seq samples" → `/samples/types` (resolve to identifier) → `/samples/search?sample_types=<identifier>`
- "samples where tissue is X" → `/samples/metadata` (does `tissue` exist on this instance? what is its actual identifier?) → `/samples/search?<identifier>=<value>`
- "samples I own" → `/samples/search?owned=true` (or `/me` first if you need the user's pk for cross-resource linking)

Why: metadata attributes are user-defined per Flow instance. There is
no global Flow vocabulary; the same product runs at different
organisations with different attribute schemas. The skill cannot
hard-code identifiers; agents must discover at runtime. See the
per-endpoint files (`endpoints/samples.md`, `endpoints/organisms.md`,
`endpoints/users.md`) for the exact response shapes.

## Pipelines

Pipelines are organised into a two-level taxonomy: categories contain
subcategories which contain pipelines (e.g. RNA-seq → bulk → nf-core/rnaseq).

`GET /pipelines` returns the full catalog as a bare JSON array (no
pagination envelope, no `page`/`count` params, no `filter` param — the
view ignores `request.GET` entirely). The response is a nested tree:
category objects each contain `subcategories`, each of which contains
`pipelines`.

Each pipeline item has `id` (stringified pk), `name`, `description` (taken
from the most recent active version), `execution_count`, `is_nfcore`, and
`prepares_genome`. The endpoint does not return the version list per
pipeline; v1 agents should not reason about specific versions.

For unauthenticated callers the catalog is filtered to pipelines that
have at least one active, non-private version. Categories and
subcategories with no surviving pipelines are dropped.

## Samples

A sample is a biological sample with metadata: organism, sample type,
project membership, and a free-form metadata bag.

**Endpoint:** `GET /samples/search`

**Visibility rule.** Unauthenticated callers see samples where
`private=False`. Authenticated callers also see samples in projects
they have access to, plus samples shared with them directly. The
endpoint applies these rules automatically — the URL is the same
regardless of auth state.

**Filter parameters.** Field-scoped, not a single free-text param.
Supported (all optional): `name` (substring on sample name), `organism`
(organism `id` from `/organisms` — a short string code like `"Hs"`, not
an integer pk — or a truthy/falsy string for has-any/has-no), `owned`
(truthy string, restricts to caller's samples), `sample_types`
(comma-separated sample-type **identifiers**), `owner` (substring across
owner name / username / group name / slug), `project` (substring on
project name), `created_gt` and `created_lt` (**Unix timestamp
integers**, e.g. `1746403200`; passing an ISO-8601 string causes HTTP
500), and any metadata attribute identifier (substring match against
that attribute's values). See `endpoints/samples.md` for the
authoritative list and exact semantics.

**Pagination.**

- `sort` (str, default `-created`). Accepts `-created` (newest first)
  and `-name`. User-controllable; sort order is not fixed.
- `page` (int, default `1`).
- `count` (int, default `10`, **max 100**). Values >100 return HTTP 400
  with `{"error": "Cannot request more than 100 items"}` — the cap is
  rejected, not silently clamped.
- Non-integer `page`/`count` values raise a 500; always pass integers.

**Response envelope:** `{"count": <int>, "page": <int>, "samples": [...]}`.
The envelope's `count` is the **total matching samples across all pages**,
not the page size. The same word `count` means "page size" in the request
and "total matches" in the response.

**Per-item fields:**

- `id` (str — stringified pk)
- `name` (str)
- `created` (int — Unix timestamp; the `Sample.created` model field is
  `IntegerField`, not a `DateTimeField`)
- `can_delete` (bool — reflects whether the caller may delete this
  sample; `false` for unauthenticated callers and for samples the
  caller does not own)
- `organism` — `{"id": str, "name": str}` or `null`
- `sample_type` — `{"identifier": str, "name": str}` or `null`
- `metadata` — object keyed by attribute identifier; each value is
  `{"attribute_name": str, "value": str|null, "annotation": str|null}`.
  Only attributes flagged `in_table=True` appear.
- `project_name` (str|null)
- `owner_name` (str|null — owner's display name, falling back to group
  owner; `null` if the sample has neither)

Filesets and individual data files are not exposed on this endpoint.

Public samples expose two sub-resources: `GET /samples/<id>/executions`
(executions the sample appears in) and `GET /samples/<id>/data` (data
files attached to the sample). Both accept `page`/`count` pagination and
a single free-text `filter` query param (case-insensitive substring
across multiple fields) — note this is the older filter shape,
*different* from `/samples/search`'s field-scoped params. Their
visibility rule for anonymous callers is **stricter** than
`/samples/search`'s: they require `sample.private == False` directly.
A private sample inside a public project is listed by `/samples/search`
but its sub-resources return 404 to anonymous callers — the two
visibility rules disagree, and this is worth flagging when the agent
hits a 404 it didn't expect. When authenticated, both sub-resources
broaden via the `readable_*` permission helpers and will return data
for any sample the caller can access.

A single sample's full record is at `GET /samples/<id>`, which is a
richer projection than the list view: it carries the **full metadata
bag** (every attribute the sample has, with `attribute_description`,
`is_list`, and `url_pattern` per attribute) rather than the
`in_table=True` subset, and it inlines the sample's filesets and their
data files. For "what metadata does sample X have" questions, the
detail endpoint is the source of truth; the list view only ever
returns in-table metadata. The detail endpoint shares the looser
visibility rule (sample OR parent project public for anonymous callers;
any accessible sample for authenticated callers),
not the stricter rule of the executions/data sub-resources.

## Projects

A project groups samples and is the top-level unit users navigate by.

**Endpoint:** `GET /projects/search`

**Visibility rule.** Unauthenticated callers see projects where
`private=False`. Authenticated callers also see projects they own
or have been shared with. The URL is the same regardless of auth state.

**Filter parameters.** Field-scoped, not a single free-text param.
Supported (all optional): `name` (substring on project name),
`description` (substring), `owner` (substring across owner name /
username / group name / slug), `sample_types` (comma-separated
sample-type **identifiers**), `pipeline` (pk for exact match —
matches if the project has any sample-level or project-level
execution of that pipeline), `created_gt` and `created_lt` (**Unix
timestamp integers**, e.g. `1746403200`; passing an ISO-8601 string
causes HTTP 500). See `endpoints/projects.md` for the authoritative
list and exact semantics.

**Pagination.** Same shape as samples:

- `sort` (str, default `-created`). Accepts `-created` (newest first)
  and `-name`. User-controllable; sort order is not fixed.
- `page` (int, default `1`).
- `count` (int, default `10`, max 100; HTTP 400 above the cap).

**Response envelope:** `{"count": <int>, "page": <int>, "projects": [...]}`.
Same overload of `count` as samples.

**Per-item fields:**

- `id` (str)
- `name` (str)
- `created` (**int — Unix timestamp**, *not* an ISO-8601 string). Same
  shape as `/samples/search`'s `created` — both endpoints store the
  timestamp on an `IntegerField`.
- `private` (bool — `false` for anonymous callers, since the queryset
  filters them out; may be `true` for authenticated callers viewing
  their own private projects)
- `description` (str)
- `sample_count` (int)
- `execution_count` (int)
- `owner_name` (str)

A single project's detail record is at `GET /projects/<id>`, which
carries the description, full owner/group_owner objects, and a
`papers` array built from the unique pubmed ids of the project's
samples. It does NOT include `sample_count` / `execution_count` (use
the list view for those numbers), and it does NOT inline a samples
list. Visibility rule: `private=False` for anonymous callers; any
accessible project for authenticated callers, same as the list view.

## Data files and downloads

Data ids are obtained by listing a public sample's files via
`GET /samples/<id>/data`. Each item carries `id` (a Data primary key),
`filename`, `size`, and a few provenance fields (pipeline, process
execution, sample). Data ids are stringified integers.

**Single-data-file detail.** `GET /data/<id>` returns the full data
record — `filetype`, `is_binary`, `is_directory`, `size`, `data_type`
(an object), the `fileset` and producing `execution` (with
`pipeline_name`, `process_name`, and the bash `process_command`), plus
the resolved `sample` and `project`. This is distinct from
`/data/<id>/contents` (text preview) and
`/downloads/<data_id>/<filename>` (file bytes); use the detail record
for "what is this file" questions. Visibility rule: any non-private
parent (sample, project, or execution) admits the call — the same rule
as the contents and download endpoints.

**Direct single-file download.** A public Data file can be downloaded
without authentication via `GET /downloads/<data_id>/<filename>`. The
`<data_id>` is a **Data id**, *not* a `BulkDownloadJob` id — the URL is
under `/downloads/` but the resource it serves is a single Data file,
which surprises people the first time. The `<filename>` segment must
equal `data.filename` exactly; mismatches return 404 with no JSON body.
The `?direct=yes` query param toggles inline display vs attachment.

**Text preview.** For non-binary, non-directory data,
`GET /data/<id>/contents` returns up to 10 KB per call as
`{"contents": str, "has_more": bool}`. The `position` query param is a
**chunk index, not a byte offset** — `position=1` returns bytes
10240–20480, `position=2` returns 20480–30720, and so on. Binary or
directory data returns HTTP 400. For full-file content, use the
download endpoint above instead of chunking through `/contents`.

**Bulk multi-file downloads are different.** The
`POST /downloads` / `POST /downloads/executions` /
`POST /downloads/samples` flow creates a `BulkDownloadJob`, runs an
async Celery task, and exposes the resulting tar.gz at
`GET /downloads/<job_id>` (a UUID, no filename segment). That entire
flow is auth-gated and out of scope here — separate from the
direct-download endpoint above.
