# Projects endpoints

Covers:

- `GET /projects/search` — list / filter
- `GET /projects/<id>` — single-project detail (description, papers, owner)

## `GET /projects/search`

The audience-agnostic projects list. Returns public projects always;
with authentication, also returns the caller's owned and shared projects.

- **Auth:** none required. Authenticated callers receive a broader
  result set automatically (no URL change).
- **Visibility rule (anonymous):** `project.private == False`. Matches
  the deprecated public endpoint exactly.
- **Visibility rule (authenticated):** the union of public projects,
  projects owned by the caller, and projects shared with the caller
  (directly or via group membership).
- **Query params:**

| Name          | Type | Default    | Behaviour |
|---------------|------|------------|-----------|
| `page`        | int  | `1`        | Paginator page. Non-integer raises 500. |
| `count`       | int  | `10`       | Page size. Max 100; >100 → HTTP 400 (not silently clamped). |
| `sort`        | str  | `-created` | Supported values: `-created` (newest first), `name`, `-name`. Other values are passed through to Django's `order_by` and may error. |
| `name`        | str  | (none)     | Substring match (`__icontains`) on project name only. |
| `description` | str  | (none)     | Substring match (`__icontains`) on project description. |
| `owner`       | str  | (none)     | Substring match (`__icontains`) across owner name, owner username, group-owner name, and group-owner slug. |
| `created_gt`  | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); project created on or after this value (`__gte`, inclusive). Passing an ISO-8601 string causes HTTP 500. |
| `created_lt`  | int  | (none)     | Unix timestamp integer (e.g. `1746403200`); project created on or before this value (`__lte`, inclusive). Passing an ISO-8601 string causes HTTP 500. |
| `sample_types`| str  | (none)     | Comma-separated sample-type **identifiers**. Matches projects that contain at least one sample whose type identifier is in the list. |
| `pipeline`    | str  | (none)     | Pipeline **pk** (exact match). Matches projects that have a sample-level or project-level execution whose pipeline version belongs to this pipeline id. |

- **No free-text `filter` parameter.** Unlike the deprecated public
  endpoint, `/projects/search` does not accept a single cross-field
  substring. The closest equivalents are `name` and
  `description` (themselves substring matches). Issue separate calls
  or pick one field to scope the search.

- **No metadata-attribute filtering.** `/projects/search` does not
  support `?<metadata_id>=<value>` filters. Metadata attributes are
  defined on samples, not projects. Any unrecognised query param is
  silently ignored — `?tissue=brain` returns the unfiltered project
  list with no error and no warning. To find projects whose samples
  carry a particular metadata value, use
  `/samples/search?<metadata_id>=<value>` and read each matching
  sample's `project_name`, or narrow by `?project=<name>` after
  discovering the project name first.

- **Response envelope:** `{"count": int, "page": int, "projects": [...]}`.
  Envelope `count` is the **total matching projects across all pages**,
  not the page size. The word `count` therefore means "page size" in the
  request and "total matches" in the response.
- **Per-item fields:**
  - `id` (str — stringified pk)
  - `name` (str)
  - `created` (**int — Unix timestamp**, NOT ISO-8601)
  - `private` (bool — `false` for public projects; may be `true` for
    owned/shared projects returned to authenticated callers)
  - `description` (str)
  - `sample_count` (int — number of samples in the project)
  - `execution_count` (int — total executions across the project's
    samples and the project itself)
  - `owner_name` (str — display name of the individual owner, or the
    group owner's name if there is no individual owner)

## `GET /projects/<id>`

Single-project detail. Use this to read a specific project's record
once the id is known (or after discovering it by name via `/projects/search`).

- **Auth:** public, no auth required.
- **Visibility rule:** anonymous callers reach the endpoint iff
  `project.private == False`. Same rule as `/projects/search` — no
  surprise. With authentication, this also returns projects the caller
  owns or has been shared with, regardless of `private`.
- **Query params:** **none**.
- **Response shape:** a **single object** (no envelope, no array).
- **Top-level fields:**
  - `id` (str)
  - `name` (str)
  - `created` (int — Unix timestamp; consistent with `/projects/search`)
  - `description` (str)
  - `private` (bool — always `false` if reachable by anonymous callers)
  - `can_edit` (bool — **always `false`** for anonymous callers; ignore)
  - `owner` — `{username, name, image}` or `null` (richer than the list
    view's flat `owner_name`)
  - `group_owner` — `{slug, name}` or `null`
  - `papers` — array of `{id, year, title, journal}`. Built from the
    unique `pubmed` ids of the project's samples by calling an external
    PubMed lookup; can be slow on first hit. May be empty.
- **Fields NOT in this projection (but present on `/projects/search`):**
  `sample_count`, `execution_count`. The detail endpoint is not a
  strict superset — use `/projects/search?name=…` if you need those
  counts.
- **No samples list inline.** This serializer does **not** include
  the project's samples. To list them, use the sub-resource
  `GET /projects/<id>/samples` (below), or filter
  `/samples/search?project=<project_name>` (substring match on project
  name).
- **Cross-link to the list view.** `/projects/search` for discovery and
  counts; this endpoint for the description-and-papers detail.

## `GET /projects/<id>/samples`

The samples that belong to a single project. Audience-agnostic
(same visibility rule as `/projects/<id>` — caller must have access
to the parent project).

- **Auth:** none required when the project is anonymous-reachable;
  authenticated callers see project-scoped private resources they
  have access to.
- **Path param:** `<id>` is the integer project pk.
- **Query params:**

| Name     | Type | Default | Behaviour |
|----------|------|---------|-----------|
| `page`   | int  | `1`     | Paginator page. |
| `count`  | int  | `10`    | Page size. Max 100; >100 → HTTP 400. |
| `filter` | str  | (none)  | **Old-style free-text filter** (case-insensitive substring across sample name and a few other fields). Different from `/samples/search`'s field-scoped params — this endpoint kept the legacy `?filter` interface. Sort is fixed at `-created`. |

- **Response envelope:** `{"count": int, "page": int, "samples": [...]}`.
  Envelope `count` is the total samples in the project visible to the
  caller, not the page size.
- **Per-item fields:** the same shape as `/samples/search`'s
  per-item projection — see `endpoints/samples.md`'s
  `GET /samples/search` "Per-item fields" list. Note that
  `project_name` is omitted from these items because the project is
  implicit in the URL.
- **404 if the project isn't visible.** Same rule as `/projects/<id>`:
  anonymous callers get 404 on private projects; authenticated callers
  get 404 on projects they have no access to.

## `GET /projects/<id>/executions`

Parallel to `/projects/<id>/samples` — lists executions associated
with a single project (executions on the project's samples, plus
project-level executions). Same auth model, same `page`/`count`/`filter`
shape. Per-item fields match `/executions/search`'s projection
(see `endpoints/executions.md`).
