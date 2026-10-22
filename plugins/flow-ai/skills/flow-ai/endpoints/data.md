# Data endpoints

Covers:

- `GET /data/<id>/contents` — text-file preview (10 KB chunks)
- `GET /data/types` — data-type discovery (list of `{identifier, name, …}`)
- `POST /upload` — **upload a generic data file**

Listing, filtering and counting data files, and one file's details, are in the
API's own reference: `GET /v2/reference/data` (see "Finding out about the API"
in `SKILL.md`). For the file bytes themselves, see `endpoints/downloads.md`.

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
  - `410 {"error": "Data <id> (<filename>) was deleted on <YYYY-MM-DD>"}` —
    the file's content was deleted under the retention policy. Report it;
    there is nothing left to preview.
- **Reading more.** Iterate `position=0`, `position=1`, … until `has_more`
  is `false`. The index is 0-based and increments by 1, not by 10240.
  Preview only; for full content, use the download endpoint
  (`endpoints/downloads.md`).

## `GET /data/types`

Discovery endpoint for the data-type enum on this instance. Resolves a
user-named data type (e.g. "FASTQ") to its `identifier`, for the data-type
filter on `GET /v2/data` and for uploads.

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

## Discovery pattern for data types

1. `GET /data/types` → list available types.
2. Match the user's term against `name` (case-insensitive) or `identifier`.
3. Pass the matched `identifier` to the data-type filter on `GET /v2/data`,
   as `GET /v2/reference/data` describes it.

## `POST /upload` — upload a generic data file

Uploads a single generic data file (counts table, BAM, archive, …).
**This is not a `curl` call** — it runs through the flowbio CLI on demand.
The runner comes from `SKILL.md` Step 0. Read
`uploading.md` first: it owns the pinned version, token discipline, base-URL
handling, and the JSON / exit-code contract. This section covers only what is specific to the
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
  confirmation** (the confirmation gate in `uploading.md`).

- **The call** (using the runner from `SKILL.md` Step 0):
  ```bash
  uvx --from flowbio==0.14.1 flowbio data upload <path> \
    [--filename NAME] [--data-type TYPE] [--directory] \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"id": "<data_id>"}`. Report the `data_id` and
  that the file is uploaded and ready. (The JSON key is `id`, not `data_id`.)

- **Errors:** a non-zero exit code carries the cause and the server message
  arrives on stderr — see the CLI contract in `uploading.md` for the exit-code table and the
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
- For a single data file's full record, use `GET /v2/data/<id>`, described in
  `GET /v2/reference/data`.
- To discover data-type identifiers, use `GET /data/types` (returns a
  flat list of `{identifier, name, description, data_count}`).
- For file bytes, see `endpoints/downloads.md`.
