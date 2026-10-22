# Worked examples — uploads & pipeline runs

Recipes that change remote state. Read `uploading.md` (CLI contract,
confirmation gate) and `endpoints/pipelines.md` (run flow) first; for
the record edits (Examples 24-25), "Changing records" in `SKILL.md` and the
topic's `/v2/reference` page.
Read-only recipes live in `examples.md`.

## Example 18: "Upload counts.tsv to Flow as a data file"

An upload, not a query. It runs through the on-demand flowbio CLI (the
`data upload` command). Read `uploading.md` and the `POST /upload` section of
`endpoints/data.md` for the full contract; the recipe below is the end-to-end
shape.

```bash
# Step 1 (optional): resolve a named data type to its identifier.
# Skip if the user gave no data type.
flowbio api get /data/types --json | \
  jq '[.[] | {identifier, name}]'

# Step 2: local pre-flight. Confirm the file exists and the stored
# filename has no spaces (the server rejects spaces with a 400).
test -f ./counts.tsv || { echo "File not found: ./counts.tsv"; exit 1; }
case "counts.tsv" in *" "*) echo "Filename has spaces — rename first."; exit 1;; esac

# Step 3: runner preflight (`SKILL.md` step 0) — prefer uv, then pipx, then
# an existing flowbio; otherwise stop with the install message.
# Step 4: CONFIRM with the user what will be uploaded (path, stored
# filename, data_type), then run the pinned CLI. The token is read by
# the CLI from ~/.config/flow/api-token — never passed as --token.
uvx --from flowbio==0.14.1 flowbio data upload ./counts.tsv \
  --json --no-progress
```

On exit `0`, parse stdout `{"id": "<data_id>"}` and report: "Uploaded
`counts.tsv` — data id `<data_id>`." On a non-zero exit, read the stderr
JSON `{"message": …, "status_code": …}` and the exit code (5 =
validation/bad request, 3 = auth, 2 = usage) and report the server
message — never claim success.

If no runner is found in step 3, stop and give the install message from
`SKILL.md` Step 0.

## Example 19: "Upload a paired-end RNA-Seq sample with metadata"

An upload, not a query — it runs through the on-demand flowbio CLI (the
`samples upload` command). Read `uploading.md` and the `POST /upload/sample`
section of `endpoints/samples.md` for the full contract. Suppose the user says:
"upload a paired-end RNA-Seq sample `liver_rep1` from `liver_R1.fastq.gz`
and `liver_R2.fastq.gz`, it's human, in my 'Liver Atlas' project, source
is liver".

```bash
# Step 1: resolve the sample type → identifier.
flowbio api get /v2/sample-types --json | \
  jq '[.[] | {identifier, name}]'
# Match "RNA-Seq" to a row; send its identifier. Ambiguous? ask the user.

# Step 2: discover which metadata attributes are REQUIRED for that type.
# Required = required_for_every_sample true OR a sample_types entry for the
# chosen identifier with required:true. Confirm the user supplied them all
# BEFORE uploading; if any is missing, name it and stop.
flowbio api get /v2/metadata-attributes --param sample_type=RNA-Seq --json | \
  jq --arg t "RNA-Seq" '[.[] | select(.required_for_every_sample or any(.sample_types[];
       .identifier == $t and .required)) | {identifier, name}]'

# Step 3: resolve organism name → id.
HUMAN_ID=$(flowbio api get /organisms --json | \
  jq -r '.[] | select(.name | ascii_downcase == "human") | .id')

# Step 4: resolve project name → id.
PROJECT_ID=$(flowbio api get /projects/search \
  --param "name=Liver Atlas" --json | \
  jq -r '.projects[0].id')

# Step 5: local pre-flight. Reads files exist; no spaces in filenames or
# the sample name (the server rejects spaces).
for f in ./liver_R1.fastq.gz ./liver_R2.fastq.gz; do
  test -f "$f" || { echo "File not found: $f"; exit 1; }
done

# Step 6: runner preflight (`SKILL.md` step 0) — prefer uv, then pipx, then an
# existing flowbio; otherwise stop with the install message.
# Step 7: CONFIRM what will be uploaded (reads files + single/paired, name,
# sample type, project, organism, metadata), then run the pinned CLI. The
# token is read by the CLI from ~/.config/flow/api-token — never --token.
uvx --from flowbio==0.14.1 flowbio samples upload \
  --name liver_rep1 --sample-type RNA-Seq \
  --reads1 ./liver_R1.fastq.gz --reads2 ./liver_R2.fastq.gz \
  --project "$PROJECT_ID" --organism "$HUMAN_ID" \
  --metadata source=liver \
  --json --no-progress
```

On exit `0`, parse stdout `{"id": "<sample_id>"}` and report: "Uploaded
sample `liver_rep1` — sample id `<sample_id>`." For a single-end sample,
omit `--reads2`. On a non-zero exit, read the stderr JSON
`{"message": …, "status_code": …}` and the exit code (5 = validation/bad
request such as an invalid sample type or missing required metadata, 3 =
auth, 2 = usage) and report the server message — never claim success.

If no runner is found in step 6, stop and give the same install message as
Example 18.

## Example 20: "Upload multiplexed reads with an annotation sheet"

An upload, not a query — it runs through the on-demand flowbio CLI (the
`samples upload-multiplexed` command). Read `uploading.md` and the
`POST /upload/multiplexed` section of `endpoints/samples.md` for the full
contract. Suppose the user says: "upload multiplexed reads `pool_R1.fastq.gz`
and `pool_R2.fastq.gz` with my annotation sheet `annotation.xlsx`, accept any
warnings".

If the user still needs an annotation sheet, download a template first
(Example 21) and let them fill it in before this step.

```bash
# Step 1: local pre-flight. Reads files and the annotation sheet exist;
# no spaces in any filename (the server rejects spaces).
for f in ./pool_R1.fastq.gz ./pool_R2.fastq.gz ./annotation.xlsx; do
  test -f "$f" || { echo "File not found: $f"; exit 1; }
  case "$f" in *" "*) echo "Filename has spaces — rename first."; exit 1;; esac
done

# Step 2: runner preflight (`SKILL.md` step 0) — prefer uv, then pipx, then an
# existing flowbio; otherwise stop with the install message.
# Step 3: CONFIRM what will be uploaded (reads files + single/paired, the
# annotation sheet, and that warnings are auto-accepted), then run the
# pinned CLI. The annotation is validated and uploaded BEFORE the reads, so
# an invalid sheet never wastes a reads upload. The token is read by the CLI
# from ~/.config/flow/api-token — never passed as --token.
uvx --from flowbio==0.14.1 flowbio samples upload-multiplexed \
  --reads1 ./pool_R1.fastq.gz --reads2 ./pool_R2.fastq.gz \
  --annotation ./annotation.xlsx \
  --json --no-progress
```

On exit `0`, parse stdout
`{"data_ids": [...], "annotation_id": "...", "warnings": [...]}` (note: no
`id` key) and report the data ids, the annotation id, and any warnings that
were auto-accepted — e.g. "Uploaded 2 multiplexed reads (`<ids>`) with
annotation `<annotation_id>`; 1 warning auto-accepted: …". For a single-end
upload, omit `--reads2`.

The user asked to accept warnings, so do **not** pass `--reject-warnings`
(warnings are auto-accepted by default). Only add `--reject-warnings` if the
user wants warnings treated as fatal.

On a non-zero exit, read the stderr JSON and the exit code. A bad request /
annotation validation error (exit `5`) carries an `errors` array of per-row
issues — show them and tell the user to fix the sheet. Because the annotation
is validated first, **no reads were uploaded** on a validation failure; never
claim success. If no runner is found in step 2, stop and give the same install
message as Example 18.

## Example 21: "Download an annotation-sheet template"

A helper for the multiplexed flow (Example 20). It changes no remote state,
so there is **no** confirmation gate. It still runs through the on-demand
flowbio CLI (the `samples annotation-template` command) so auth and base-URL
handling stay uniform. Read the `GET /annotation/<sample_type>` section of
`endpoints/samples.md`. Suppose: "download the RNA-Seq annotation template to
`./template.xlsx`".

```bash
# Step 1: resolve the sample type → identifier (skip for the generic template).
flowbio api get /v2/sample-types --json | \
  jq '[.[] | {identifier, name}]'
# Match "RNA-Seq" to a row; send its identifier. Ambiguous? ask the user.

# Step 2: runner preflight (`SKILL.md` step 0) — prefer uv, then pipx, then an
# existing flowbio; otherwise stop with the install message. No confirmation
# needed — this is a read. The token is read by the CLI from
# ~/.config/flow/api-token — never passed as --token.
uvx --from flowbio==0.14.1 flowbio samples annotation-template \
  --sample-type rna_seq -o ./template.xlsx \
  --json --no-progress
```

On exit `0`, parse stdout `{"output": "./template.xlsx", "sample_type":
"rna_seq"}` and report where the template was written, plus that the user
should fill in one row per sample (names, file paths, metadata) before running
the multiplexed upload (Example 20). Omit `--sample-type` for the `generic`
template (base columns only). On a non-zero exit, read the stderr JSON and the
exit code (`4` = unknown sample type — re-resolve via `/v2/sample-types`; `3` =
auth; `2` = usage) — never claim success. If no runner is found in step 2, stop
and give the same install message as Example 18.

## Example 22: "Run the rna-seq pipeline on sample Liver_RNA_1"

Running a pipeline is a **mutation** and **always needs the token**. The
discovery steps are reads via `flowbio api get`; the run itself is one
`flowbio api post`. Read the "Running a pipeline" section of
`endpoints/pipelines.md` first — it owns the body shape, the schema→body
mapping, the confirmation gate, and the error table. The chain:

```bash
# Step 0: confirm auth — running always needs the token.
flowbio api get /me --json | jq '.id'
# null → token missing/expired; stop and tell the user how to authenticate.

# Step 1: find the pipeline id by name.
flowbio api get /pipelines --json | \
  jq '[.. | objects | select(.name? | test("rna.?seq"; "i")) | select(.id?)] | .[] | {id, name}'

# Step 2: pick the version — default to the most recent (versions[0]).
flowbio api get /pipelines/<pipeline_id> --json | \
  jq '{name, default_version: .versions[0], nextflow: .versions[0].nextflow_versions[0]}'

# Step 3: read the version schema to learn the params.
flowbio api get /pipelines/versions/<version_id> --json | \
  jq '{nextflow_versions, inputs: [.schema.inputs[] | {name, params: (.params|keys)}]}'

# Step 4: resolve the sample name → id (for the samplesheet csv param).
flowbio api get /samples/search \
  --param name=Liver_RNA_1 --json | \
  jq '.samples[] | {id, name}'
```

Now build the body from the schema (see the mapping in `endpoints/pipelines.md`).
For a typical nf-core-style pipeline whose input is a `csv` `takes_samples`
samplesheet, you usually only need the sample id per row — the server fills
`from_sample` columns itself. Default the Nextflow version to
`nextflow_versions[0]` since the user didn't name one.

**Confirm first** — show the pipeline, version (name + id), the resolved params
(sample *names*, not just ids), and the Nextflow version, and proceed only on
explicit "yes". Then:

```bash
printf '%s' '{"params":{},"data_params":{},"csv_params":{"input":{"rows":[{"sample":"SAMPLE_ID","values":{}}]}},"nextflow_version":"23.04.3"}' | uvx --from flowbio==0.14.1 flowbio api post /pipelines/versions/VERSION_ID/run --body - --json | jq '{id, identifier, status}'
```

On success, report the execution `id`, `identifier`, initial `status`, and a
link to the run in the UI — derive it by stripping a trailing `/api` from the
base URL:

```bash
WEB="${FLOW_API_URL:-https://app.flow.bio/api}"; WEB="${WEB%/api}"
echo "$WEB/executions/<id>/"   # e.g. https://app.flow.bio/executions/<id>/
```

**Do not poll by default** — return the id and the link and stop. On `403`
(`User cannot run pipelines` or `Token not authorised for this endpoint`) report
it verbatim and stop; on `400` report the field error and fix the offending
value before re-confirming. Never claim a run started on a non-zero exit.

## Example 23: "Run the rnaseq pipeline and tell me when it finishes"

Same as Example 22 through the POST, but the user asked to be notified on
completion, so **poll** afterwards. Poll on a slow cadence — runs commonly take
hours.

```bash
# After the run returns <id>, poll status on a >=60s interval until terminal.
flowbio api get /executions/<id> \
  --param include=status --param include=finished --json | \
  jq '{status, finished}'
# Repeat (sleep >= 60s between calls) until status is OK, ERROR, or CANCELED.
```

On `OK`, report success (optionally tail the log with `--param log=<offset>`). On
`ERROR`, fetch and surface `stderr` / `log` / the failing `process_executions`
entry — never report success on a non-`OK` terminal status. See the
`GET /executions/<id>` section of `endpoints/executions.md`.

## Example 24: "Set the cell line of sample liver_rep1 to HepG2"

A record edit. Read `/v2/reference/samples` first; it says which attributes
apply to the sample's type and how the edit reports a refused value.

```bash
# Step 1: resolve the sample by name to its id.
flowbio api get /samples/search --param name=liver_rep1 --param count=10 --json | \
  jq -r '.samples[] | .id + " | " + .name + " | " + .sample_type.identifier'
# More than one match? Ask the user which.

# Step 2: find the attribute the user means, by its name.
flowbio api get /v2/metadata-attributes --json | \
  jq -r '.[] | .identifier + " | " + .name + " | " + (.has_options | tostring)'

# Step 3: it has options, so check the value is one of them.
flowbio api get /v2/metadata-attributes/cell_line/options --param value=HepG2 --json | \
  jq -r '.items[].value'
# The filter matches substrings, so check one value is exactly HepG2 (not
# HepG2-C3A). None is, and the attribute has no allow_user_terms? Tell the user.

# Step 4: CONFIRM with the user: sample liver_rep1, cell_line → HepG2. Then
# send only that attribute; everything else on the sample keeps its value.
# One line of JSON in single quotes; write an apostrophe in a value as \u0027.
printf '%s' '{"metadata": {"cell_line": {"value": "HepG2"}}}' | \
  uvx --from flowbio==0.14.1 flowbio api patch /v2/samples/SAMPLE_ID --body - --json | \
  jq '{id, name, cell_line: .metadata.cell_line}'
```

Report the value from the response. A 422 lists each problem with its
`pointer`: `/metadata/cell_line` is a value the attribute refuses (for example,
one not among its options), `/metadata/<identifier>` with code
`unknown_attribute` an identifier this instance does not have. Report the
`detail`; never claim success.

## Example 25: "Create a project called Liver Atlas"

A record creation. Read `/v2/reference/projects` first.

```bash
# CONFIRM with the user: project "Liver Atlas", description "Bulk RNA-Seq of
# liver tissue", private (say public only if the user asked for it).
printf '%s' '{"name": "Liver Atlas", "description": "Bulk RNA-Seq of liver tissue"}' | \
  uvx --from flowbio==0.14.1 flowbio api post /v2/projects --body - --json | \
  jq '{id, name}'
```

Report the new project's id. A 422 pointing at `/name` means the user already
has a project with that name: report it and ask, rather than picking another
name. To make the project public, add `"private": false` to the body, and only
when the user asked for it; an existing project's visibility is changed only in
the Flow web app.
