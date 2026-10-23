# Uploading data to Flow

The skill can upload data to Flow. Upload support currently covers a
**generic data file** (`POST /upload`), a **demultiplexed sample**
(`POST /upload/sample`), and **multiplexed reads + an annotation sheet**
(`POST /upload/multiplexed`), plus a read-only **annotation-sheet template**
download (`GET /annotation/<sample_type>`) that bootstraps the multiplexed flow.
More upload types will be added to this file over time — an upload type is
available only once it is documented here. This section holds the cross-cutting
upload machinery; the per-resource specifics (inputs, local validation,
success/error shapes) live in the matching endpoint file — generic files →
`endpoints/data.md`, samples / multiplexed / annotation templates →
`endpoints/samples-upload.md`.

Uploads are **not** done with `curl`. The chunked/resumable upload protocol
(retry, backoff, token refresh) is owned by the **flowbio** Python library; the
skill shells out to that library's command-line interface and never
reimplements the protocol in bash, nor improvises Python at runtime. The
`flowbio` version `flow-cli` runs carries the upload commands `data upload`,
`samples upload`, `samples upload-multiplexed` and `samples annotation-template`.

## Running the CLI

Uploads go through `flow-cli`, like every other call, once `SKILL.md` Step 0
has checked it works. If Step 0 finds no working CLI, stop and give the user
its message; never attempt the upload another way.

##  Auth & base URL (token discipline preserved)

- **Token.** The CLI reads `~/.config/flow/api-token` itself — the same file
  the read endpoints use ("Authentication" in `SKILL.md`). **Do not pass `--token`, and never
  `cat`/`echo`/print the token.** Let the CLI read the file. If the file is
  absent the CLI exits with an auth error (exit `3`); report that the token is
  missing rather than improvising one.
- **Base URL.** The CLI honours `FLOW_API_URL` (default
  `https://app.flow.bio/api`). Forward it only when the user has overridden it.
- Always pass `--json` (one machine-readable document on stdout) **and**
  `--no-progress` (keep progress bars out of the transcript).

##  CLI contract — what to parse

- **Success:** exit `0`, with one machine-readable JSON document on stdout. The
  shape depends on the command — parse the right one:
  - `data upload` and `samples upload` → `{"id": "<id>"}`. The `id` is a
    `data_id` for a generic file and a `sample_id` for a sample. The key is
    always `id`, **not** `data_id` / `sample_id`.
  - `samples upload-multiplexed` → `{"data_ids": ["…"], "annotation_id": "…",
    "warnings": [...]}`. Report the data ids, the annotation id, and any
    `warnings` (these were auto-accepted unless `--reject-warnings` was set).
    There is **no** `id` key here.
  - `samples annotation-template` → `{"output": "<path>", "sample_type": "…"}`.
    Report where the template was written. No `id` key.
- **Failure:** non-zero exit; stderr carries `{"message": …, "status_code": …}`
  when the error came from the server. Annotation validation failures
  additionally carry `errors`: a list with one entry per sample row, in sheet
  order, mapping a column header to that cell's messages, and `{}` for a row
  with no problems — e.g. `[{}, {"Sample Name": ["'Sample 1' has spaces in
  it."], "Source": ["This field is required."]}]` means the second sample is
  wrong. A problem with the sheet as a whole (unknown columns, no rows) comes
  as a single string instead. Surface each problem with its sample. The
  `message` here ("Annotation has N validation error(s)") counts rows, not
  problems, so count the non-empty entries yourself. Otherwise report the
  server `message` verbatim. Map the exit code to the cause — never fabricate
  success:

  | Exit | Meaning |
  |------|---------|
  | `0` | Success |
  | `1` | API / runtime error |
  | `2` | Usage / input error (e.g. file not found, bad flags) |
  | `3` | Authentication failed (token missing or expired) |
  | `4` | Not found (e.g. unknown sample type for a template) |
  | `5` | Bad request / validation (e.g. spaces in filename, invalid data-type, annotation-sheet validation errors) |

##  Confirmation gate

Uploads change remote state. Before running any upload command, show the user
exactly what will be uploaded and proceed **only on explicit confirmation**.
Read and discovery calls need no confirmation. What to show depends on the
upload type:

- **Generic data file** (`POST /upload`): the file path, the stored `filename`
  if overridden, and the `data_type` if given.
- **Demultiplexed sample** (`POST /upload/sample`): the reads file(s) and
  whether the sample is single- or paired-end, the sample `name`, the resolved
  sample type, the project and organism (if given), and the metadata
  key/values.
- **Multiplexed reads** (`POST /upload/multiplexed`): the reads file(s) and
  whether single- or paired-end, the annotation-sheet path, and whether warnings
  are auto-accepted (default) or rejected (`--reject-warnings`).

Downloading an annotation-sheet template (`GET /annotation/<sample_type>`) is a
read — it changes no remote state, so it needs **no** confirmation.

