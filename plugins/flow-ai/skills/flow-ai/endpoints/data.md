# Data endpoints

Covers:

- `GET /data/<id>` — single data-file detail (type, size, fileset and execution links)
- `GET /data/<id>/contents` — text-file preview (10 KB chunks)
- `GET /data/types` — data-type discovery (list of `{identifier, name, …}`)
- `POST /upload` — **upload a generic data file**

For the file bytes themselves, see `endpoints/downloads.md`.

## `GET /data/<id>`

Single data-file detail. The full record for a Data row: type, size,
fileset and execution links. Use this when the user asks about a
specific file by id (or after listing a sample's files via
`/samples/<id>/data` to discover the id).

- **Auth:** public when the data is anonymous-readable. The endpoint
  walks the data's parents (upstream execution, project, fileset.sample)
  and admits the call iff some parent is non-private — the same rule as
  `/data/<id>/contents` and `/downloads/<data_id>/<filename>`.

**With authentication:** any data the caller owns, has access to via
the parent project/sample/execution, or has been shared resolves
through this endpoint. URL unchanged.

- **Filter:** view restricts to `is_removed=False, is_ready=True`.
  Soft-deleted or not-yet-ready data → 404.
- **Query params:** **none**.
- **Response shape:** a **single object**.
- **Top-level fields:**
  - `id` (str)
  - `filename` (str)
  - `filetype` (str — Flow's filetype string, e.g. `"fastq"`, `"html"`)
  - `size` (int — bytes)
  - `is_binary` (bool)
  - `is_directory` (bool)
  - `created` (int — Unix timestamp)
  - `category` (int — Data category code; not documented as an enum here)
  - `data_type` — `{identifier, name, description}` or `null`
  - `private` (bool — `false` if a public parent forces it public)
  - `absolute_path` (str — Flow-internal server-side path; do not
    surface this to the user)
  - `owner` — `{username, name, image}` or `null`
  - `group_owner` — `{slug, name}` or `null`
  - `paired` — `{id, filename}` or `null` (only when the fileset has
    exactly two ready, non-removed data items; identifies the other
    one — useful for paired-end FASTQs)
  - `fileset` — `{id, name}` or `null`
  - `execution` — `{id, pipeline_name, process_name, process_command}` or
    `null`. Present when the data was produced by a pipeline.
    `process_command` is the **bash command** for the producing process.
    Note this exposes shell text on a public endpoint; surface it only
    when the user explicitly asks, and report it as the producing
    process's command rather than rich execution metadata. The broader
    "no command/logs" guidance for the executions view itself
    (see `endpoints/samples.md`) still holds there.
  - `sample` — `{id, name}` or `null` (the producing or owning sample,
    resolved through the upstream chain)
  - `project` — `{id, name}` or `null`
  - `can_edit` (bool — **always `false`** for anonymous callers; ignore)
- **Cross-link to the list view.** `/samples/<id>/data` gives a
  trimmed table-row view; this endpoint gives the full record. For
  "tell me about file X", prefer this. For text content of a file use
  `/data/<id>/contents` (below); for the file bytes use
  `endpoints/downloads.md`.

## `GET /data/<id>/contents`

- **Auth:** public when the data is anonymous-readable. The endpoint walks
  the data's parents (process execution, execution, project, fileset.sample)
  and admits the call iff some parent is non-private.

**With authentication:** any data the caller owns, has access to via
the parent project/sample/execution, or has been shared is readable
through this endpoint. URL unchanged.

- **Query params:**

| Name       | Type | Default | Behaviour |
|------------|------|---------|-----------|
| `position` | int  | `0`     | **Chunk index, NOT a byte offset.** `position=0` returns bytes 0–10240, `position=1` returns 10240–20480, and so on. Non-integer raises 500. |

- **Chunk size:** fixed at 10 KB (10240 bytes) per call. Not configurable.
- **Response envelope:** `{"contents": str, "has_more": bool}`. `contents` is
  up to 10 KB of decoded text; `has_more` is `true` iff more bytes follow.
- **Refusals:**
  - `400 {"error": "Data is binary"}` — the data is flagged binary.
  - `400 {"error": "Data is directory"}` — the data is a directory listing,
    not a file.
  - `404 {"error": "Not found"}` — id missing, removed, not yet ready, or no
    parent is non-public for an anonymous caller.
- **Reading more.** Iterate `position=0`, `position=1`, … until `has_more`
  is `false`. The index is 0-based and increments by 1, not by 10240.
  Preview only; for full content, use the download endpoint
  (`endpoints/downloads.md`).

## `GET /data/types`

Discovery endpoint for the data-type enum on this instance. Resolves a
user-named data type (e.g. "FASTQ") to its `identifier` for the
`?data_types=<identifiers>` filter on `/data/search`.

Small, finite list per instance — may be empty if no types are
configured.

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array (not paginated).
- **Per-item fields:**
  - `identifier` (str — the filter key, e.g. `"fastq"`)
  - `name` (str — human-readable label)
  - `description` (str)
  - `data_count` (int — number of ready, non-removed Data rows with this type)

Note: `/data/types/<identifier>` does **not** exist as a read endpoint —
there is no detail route for individual data types. Use the list
endpoint and match by `identifier` client-side.

## `GET /data/search`

Cross-sample data search. Distinct from `/samples/<id>/data` (which
scopes to a single sample). Use this when the user asks about data
files broadly ("find all FASTQ files", "find data files uploaded
this week").

- **Auth:** none required for public data; authenticated callers see
  data on resources they have access to.
- **Visibility rule (anonymous):** data on samples / projects /
  executions where some parent isn't private — same rule as
  `/data/<id>`.
- **Visibility rule (authenticated):** the union of public data and
  data the caller owns / has access to via the parent.
- **Query params:**

| Name                | Type | Default     | Behaviour |
|---------------------|------|-------------|-----------|
| `page`              | int  | `1`         | Paginator page. |
| `count`             | int  | `10`        | Page size. Max 100; >100 → HTTP 400. |
| `sort`              | str  | `"-created"` | Sort field. Supported values: `created`, `-created`, `filename`, `-filename`. Any other value is passed raw to the ORM and will likely cause a 500. |
| `filename`          | str  | (none)      | Case-insensitive substring match on filename. |
| `pattern`           | str  | (none)      | **Regex** match on filename (Django `__regex`). Non-overlapping with `filename` — both filters are applied independently when both are supplied. |
| `owned`             | str  | (none)      | Truthy string (`"true"`, `"yes"`, `"1"`) restricts to data owned by the authenticated caller. Requires authentication; if unauthenticated it silently filters to nothing. |
| `uploaded`          | str  | (none)      | Truthy string restricts to user-uploaded data (i.e. data with no upstream process execution, not produced by a pipeline). |
| `is_single`         | str  | (none)      | `"true"` / `"yes"` / `"1"` → only data that is the sole file in its fileset (or has no fileset). `"false"` / `"no"` / `"0"` → only data whose fileset has multiple files (paired reads etc.), returning the first of each pair (`fileset_order=1`). When `is_single=false`, the response item gains a `paired_filename` field. |
| `category`          | int  | (none)      | Filter by data category integer. Known values: `1` = generic, `2` = annotation, `3` = multiplexed, `4` = demultiplexed. |
| `data_types`        | str  | (none)      | Comma-separated list of data-type identifiers (e.g. `"fastq,bam"`). Matches data whose `data_type.identifier` is in the list. Discover valid identifiers via `GET /data/types`. |
| `size_gt`           | int  | (none)      | **Bytes** (integer). Inclusive lower bound on file size (`size >= size_gt`). |
| `size_lt`           | int  | (none)      | **Bytes** (integer). Inclusive upper bound on file size (`size <= size_lt`). |
| `created_gt`        | int  | (none)      | **Unix timestamp integer** (NOT ISO-8601 — passing an ISO-8601 string causes HTTP 500). Inclusive lower bound on creation time. |
| `created_lt`        | int  | (none)      | **Unix timestamp integer**. Inclusive upper bound on creation time. |
| `owner`             | str  | (none)      | Case-insensitive substring match against the owner's name, username, group name, or group slug. |
| `process_execution` | str  | (none)      | Case-insensitive substring match on the producing process execution's `process_name`. |
| `pipeline`          | str  | (none)      | Exact pipeline ID. Restricts to data produced by executions of that pipeline. |

- **No free-text `filter` parameter.** Filtering is field-scoped.
- **Response envelope:** `{"count": int, "page": int, "data": [...]}`.
  The array key is `data` (not `samples`/`projects`/`executions`).
  `count` is the total number of matching files across all pages.
- **Per-item fields** (from `data_list()` serializer):
  - `id` (str)
  - `filename` (str)
  - `size` (int — bytes)
  - `absolute_path` (str — Flow-internal server-side path; do not surface to the user)
  - `created` (int — Unix timestamp)
  - `pipeline_name` (str|null — name of the pipeline that produced this file)
  - `process_execution_name` (str|null — name of the producing process step)
  - `sample_name` (str|null)
  - `owner_name` (str — always present; owner's display name or group name)
  - `can_delete` (bool — `false` for anonymous callers)
  - `paired_filename` (str|null — **only present when `is_single=false`**; filename of the paired file in the fileset)

Note: the search list view returns fewer fields than the detail view (`/data/<id>`). Fields like `filetype`, `data_type`, `execution`, `project`, and `fileset` are not included.

## Discovery patterns

- "Find all FASTQ files" → use `?filename=fastq` (substring match) or
  `?pattern=\\.f(ast)?q(\\.gz)?$` (regex). For type-exact matching,
  discover identifiers via `GET /data/types` then use `?data_types=<identifier>`.
- "Find files larger than 1 GB" → `?size_gt=1073741824` (size in bytes).
- "Find data files from this week" → compute Unix timestamps for the
  week boundaries and use `?created_gt=<start>&created_lt=<end>`.
- "Find my uploaded files" → `?owned=true&uploaded=true` (requires authentication).
- "Find data produced by process X" → `?process_execution=<substring>`.

## Discovery pattern for data types

1. `GET /data/types` → list available types.
2. Match the user's term against `name` (case-insensitive) or `identifier`.
3. Pass the matched `identifier` to
   `/data/search?data_types=<identifier>` (comma-separated for multiple).

## `POST /upload` — upload a generic data file

Uploads a single generic data file (counts table, BAM, archive, …).
**This is not a `curl` call** — it runs through the flowbio CLI on demand.
Read **SKILL.md section 4** first: it owns
the runner preflight (`uv`/`uvx` → `pipx` → existing `flowbio` → stop with an
install message), the pinned version, token discipline, base-URL handling, and
the JSON / exit-code contract. This section covers only what is specific to the
data-file call.

- **Inputs:**
  - `path` (required) — the local file to upload.
  - `--filename NAME` (optional) — override the name the file is stored under
    on Flow. Defaults to the local file's name. Must contain no spaces.
  - `--data-type TYPE` (optional) — a `DataType` **identifier**. Discover valid
    identifiers via `GET /data/types` (above) and match the user's term to an
    `identifier`. Sent as-is and validated **server-side** — the CLI does not
    pre-check it.
  - `--directory` (optional) — treat `path` as an archive (`.zip`/`.tar`/
    `.tar.gz`) the server unpacks. Only pass this when the file really is an
    archive the user wants unpacked.

- **Local pre-flight (before running the CLI):**
  - Confirm the file exists.
  - Confirm the **stored** filename (the local name, or `--filename` if given)
    has **no spaces** — the server rejects spaces with a `400`. Tell the user to
    rename rather than attempting the upload.
  - If a `data_type` was named, optionally resolve it against `GET /data/types`
    so an obvious typo is caught before the round-trip (the server is still the
    authority).

- **Confirmation:** show the user the file path, the stored `filename` (if
  overridden), and the `data_type` (if any), and upload **only on explicit
  confirmation** (SKILL.md §4.4).

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from "flowbio==0.6.0" flowbio data upload <path> \
    [--filename NAME] [--data-type TYPE] [--directory] \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"id": "<data_id>"}`. Report the `data_id` and
  that the file is uploaded and ready. (The JSON key is `id`, not `data_id`.)

- **Errors:** a non-zero exit code carries the cause and the server message
  arrives on stderr — see **SKILL.md §4.3** for the exit-code table and the
  JSON error shape. The data-file-specific causes to recognise:
  - **Bad request / validation** — spaces in the filename
    (`{"filename": ["Spaces in filename"]}`), an invalid `data_type`, or an
    ownership rejection. Report the server field message verbatim.
  - **Auth** — the token is missing or expired; `~/.config/flow/api-token` is
    absent or stale.
  - **Usage** — e.g. the local file was not found.
  Never report success on a non-zero exit.

## Cross-links

- For data on a specific sample, use `/samples/<id>/data`
  (see `endpoints/samples.md`).
- For a single data file's full record (including `data_type`, `fileset`,
  `execution` details), use `/data/<id>` (above in this file).
- To discover data-type identifiers, use `GET /data/types` (returns a
  flat list of `{identifier, name, description, data_count}`).
- For file bytes, see `endpoints/downloads.md`.
