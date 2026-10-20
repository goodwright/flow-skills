# Samples — uploads & annotation templates

- `POST /upload/sample` — upload a demultiplexed sample
- `POST /upload/multiplexed` — upload multiplexed reads + an annotation sheet
- `GET /annotation/<sample_type>` — download an annotation-sheet template

All three go through the flowbio CLI. Read `uploading.md` first for the runner
preflight, auth, CLI contract, and the confirmation gate.

## `POST /upload/sample` — upload a demultiplexed sample

Uploads a single demultiplexed sample (single-end or paired-end reads plus
metadata). **This is not a `curl` call** — it runs through the flowbio CLI on
demand. Read `uploading.md` first: it owns the runner preflight
(`uv`/`uvx` → `pipx` → existing `flowbio` → stop with an install message), the
pinned version, token discipline, base-URL handling, and the JSON / exit-code
contract. This section covers only what is specific to the sample call.

- **Inputs / flags:**
  - `--name NAME` (required) — the sample name. Must contain no spaces (the
    server rejects them).
  - `--sample-type IDENTIFIER` (required) — a sample-type **identifier**.
    Discover and resolve it via `GET /v2/sample-types` — match the user's
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
    flag. Keys are attribute `identifier`s from `GET /v2/metadata-attributes`.

- **Discovery + local pre-flight (before running the CLI)** — reuse the
  existing read endpoints; **discover before uploading, never guess**:
  - **Sample type** — `GET /v2/sample-types`; resolve the user's term to an
    `identifier`. Surface ambiguous matches to the user instead of guessing.
  - **Required metadata** — `GET /v2/metadata-attributes --param
    sample_type=<identifier>` lists the attributes the chosen type may carry. An
    attribute is required for that type if its `required_for_every_sample` is
    `true` **OR** a `sample_types` entry whose `identifier` matches the chosen
    type has `required: true` (`/v2/reference/samples` states the full rules).
    Confirm the user supplied every such attribute **before** uploading; if any
    is missing, name it (by `identifier`/`name`) and stop. Into a public
    project, a sample is public too, so the attributes with
    `required_for_public` (or a matching link's) are required as well. For an attribute
    with `has_options`, check the user's value against
    `GET /v2/metadata-attributes/<identifier>/options`; for `regex_validator`,
    validate what you can locally. The **server is the final authority**.
  - **Organism** — `GET /organisms`; resolve name / latin name → `id`.
  - **Project** — `GET /projects/search`; resolve name → `id`.
  - **Files & names** — confirm `reads1` (and `reads2` if given) exist, and
    that the reads filenames and the sample `name` contain **no spaces**. Tell
    the user to rename rather than attempting the upload.

- **Confirmation:** show the user the reads file(s) and whether the sample is
  single- or paired-end, the sample `name`, the resolved sample type, the
  project and organism (if given), and the metadata key/values — and upload
  **only on explicit confirmation** (the confirmation gate in `uploading.md`).

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from flowbio==0.14.0 flowbio samples upload \
    --name NAME --sample-type IDENTIFIER \
    --reads1 PATH [--reads2 PATH] \
    [--project ID] [--organism ID] [--metadata KEY=VALUE ...] \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"id": "<sample_id>"}`. Report the `sample_id`
  and that the sample is uploaded. (The JSON key is `id`, not `sample_id`.)

- **Errors:** a non-zero exit code carries the cause and the server message
  arrives on stderr — see the CLI contract in `uploading.md` for the exit-code table and the
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
base-URL handling stay uniform with the uploads. Read `uploading.md`
first for the runner preflight, token discipline, and the JSON / exit-code
contract.

- **Inputs / flags:**
  - `--sample-type IDENTIFIER` (optional, default `generic`) — a sample-type
    **identifier**. A type-specific template (e.g. `rna_seq`) includes columns
    for that type's metadata attributes; `generic` includes only the base
    columns common to all types. Resolve a user's natural-language type via
    `GET /v2/sample-types` and send the `identifier`. Sent as-is and
    validated **server-side**.
  - `-o PATH` / `--output PATH` (required) — the file to write the `.xlsx`
    workbook to (the template is binary).

- **Discovery (before running the CLI):** if the user named a sample type,
  resolve it to an `identifier` via `GET /v2/sample-types`; surface ambiguous
  matches instead of guessing. If they gave none, use `generic`.

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from flowbio==0.14.0 flowbio samples annotation-template \
    --sample-type IDENTIFIER -o ./template.xlsx \
    --json --no-progress
  ```

- **Success:** exit `0`, stdout `{"output": "<path>", "sample_type": "<id>"}`.
  Report where the template was written and that the user should fill in one row
  per sample (names, file paths, metadata) before running the multiplexed
  upload. There is **no** `id` key.

- **Errors:** a non-zero exit carries the cause and any server message on stderr
  (see the CLI contract in `uploading.md`). The template-specific causes:
  - **Not found** (exit `4`) — the sample type does not exist; re-resolve via
    `GET /v2/sample-types`.
  - **Auth** (exit `3`) — the token is missing or expired.
  - **Usage** (exit `2`) — e.g. the output path is not writable.
  Never report success on a non-zero exit.

## `POST /upload/multiplexed` — upload multiplexed reads + an annotation sheet

Uploads one or two multiplexed reads files plus a completed annotation sheet for
server-side demultiplexing. **This is not a `curl` call** — it runs through the
flowbio CLI on demand. Read `uploading.md` first: it owns the runner
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
  confirmation** (the confirmation gate in `uploading.md`).

- **The call** (using whichever runner the preflight selected):
  ```bash
  uvx --from flowbio==0.14.0 flowbio samples upload-multiplexed \
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
  arrives on stderr — see the CLI contract in `uploading.md` for the exit-code table and the
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
