# Worked examples — uploads & pipeline runs

Recipes that change remote state. Read `uploading.md` (CLI contract,
confirmation gate) and `endpoints/pipelines.md` (run flow) first; for
the record edits (Examples 24-25), "Changing records" in `SKILL.md` and the
topic's `/v2/reference` page.
Read-only recipes live in `examples.md`.

Every command follows SKILL.md's rules: one line, no `VAR=…` assignments, and
`flow-cli` for every Flow call. Words in capitals (`TYPE_IDENTIFIER`,
`PROJECT_ID`) are placeholders: replace each with the value a previous command
printed, never with a guess. Check the CLI once per session first (SKILL.md
Step 0); if Step 0 finds no working CLI, stop and give the user its message.

## Example 18: "Upload counts.tsv to Flow as a data file"

An upload, not a query. It runs through the on-demand flowbio CLI (the
`data upload` command). Read `uploading.md` and the `POST /upload` section of
`endpoints/data.md` for the full contract; the recipe below is the end-to-end
shape.

If the user named a data type, find its identifier; skip this otherwise:

```bash
flow-cli api get /data/types --json | jq -r '.[] | .identifier + " | " + .name'
```

Check the file exists and that its name has no spaces (the server rejects
spaces with a 400; tell the user to rename it rather than uploading):

```bash
ls -l ./counts.tsv
```

**Confirm with the user** what will be uploaded — the path, the stored filename
if overridden, the data type if given — then upload. The CLI reads the token
itself; never pass `--token`.

```bash
flow-cli data upload ./counts.tsv --json --no-progress
```

Add `--data-type DATA_TYPE` when the user named one. On exit `0`, parse stdout
`{"id": "<data_id>"}` and report: "Uploaded `counts.tsv` — data id
`<data_id>`." On a non-zero exit, read the stderr JSON
`{"message": …, "status_code": …}` and the exit code (5 = validation/bad
request, 3 = auth, 2 = usage) and report the server message — never claim
success.

## Example 19: "Upload a paired-end RNA-Seq sample with metadata"

An upload, not a query — it runs through the on-demand flowbio CLI (the
`samples upload` command). Read `uploading.md` and the `POST /upload/sample`
section of `endpoints/samples-upload.md` for the full contract. Suppose the user
says: "upload a paired-end RNA-Seq sample `liver_rep1` from `liver_R1.fastq.gz`
and `liver_R2.fastq.gz`, it's human, in my 'Liver Atlas' project, source is
liver".

1. **The sample type.** Match the user's "RNA-Seq" to a row's name and use that
   row's identifier as `TYPE_IDENTIFIER`. Identifiers differ between Flow
   instances, so look it up in this session every time. Ambiguous? Ask the user.

   ```bash
   flow-cli api get /v2/sample-types --json | jq -r '.[] | .identifier + " | " + .name'
   ```

2. **The metadata that type requires.** An attribute is required when
   `required_for_every_sample` is true or its `sample_types` entry for this type
   says `required`. Check the user gave every required one **before**
   uploading; if any is missing, name it and stop.

   ```bash
   flow-cli api get /v2/metadata-attributes --param sample_type=TYPE_IDENTIFIER --json | jq -r --arg t TYPE_IDENTIFIER '.[] | .identifier + " | " + .name + " | " + (.description // "") + " | required: " + ((.required_for_every_sample or any(.sample_types[]; .identifier == $t and .required)) | tostring)'
   ```

3. **The organism.** Pick the user's from the list by reading the rows:

   ```bash
   flow-cli api get /organisms --json | jq -r '.[] | .id + " | " + .name + " | " + .latin_name'
   ```

4. **The project.** "My project" needs a working token: without one the search
   sees public projects only, and a private project looks missing. Check it
   first; on a 401 (exit 3) or `NO ID`, stop and tell the user how to
   authenticate:

   ```bash
   flow-cli api get /me --json | jq -r '.id // "NO ID"'
   ```

   `name` is a substring match, so pick the row whose name is exactly the
   user's ("Liver Atlas" also matches "Public Liver Atlas"). Quote a value that
   contains a space. No exact match, or more than one? Ask the user.

   ```bash
   flow-cli api get /projects/search --param "name=Liver Atlas" --param count=100 --json | jq -r '.projects[] | .id + " | " + .name'
   ```

5. **The files.** Check both exist, and that neither the filenames nor the
   sample name contain spaces (the server rejects spaces):

   ```bash
   ls -l ./liver_R1.fastq.gz ./liver_R2.fastq.gz
   ```

6. **Confirm with the user** what will be uploaded — the reads files and that
   the sample is paired-end, the name, the sample type, the project, the
   organism and the metadata — then upload. For a single-end sample, leave out
   `--reads2`.

   ```bash
   flow-cli samples upload --name liver_rep1 --sample-type TYPE_IDENTIFIER --reads1 ./liver_R1.fastq.gz --reads2 ./liver_R2.fastq.gz --project PROJECT_ID --organism ORGANISM_ID --metadata source=liver --json --no-progress
   ```

On exit `0`, parse stdout `{"id": "<sample_id>"}` and report: "Uploaded
sample `liver_rep1` — sample id `<sample_id>`." On a non-zero exit, read the
stderr JSON `{"message": …, "status_code": …}` and the exit code (5 =
validation/bad request such as an invalid sample type or missing required
metadata, 3 = auth, 2 = usage) and report the server message — never claim
success.

## Example 20: "Upload multiplexed reads with an annotation sheet"

An upload, not a query — it runs through the on-demand flowbio CLI (the
`samples upload-multiplexed` command). Read `uploading.md` and the
`POST /upload/multiplexed` section of `endpoints/samples-upload.md` for the full
contract. Suppose the user says: "upload multiplexed reads `pool_R1.fastq.gz`
and `pool_R2.fastq.gz` with my annotation sheet `annotation.xlsx`, accept any
warnings".

If the user still needs an annotation sheet, download a template first
(Example 21) and let them fill it in before this step.

Check the reads files and the sheet exist, and that no filename contains a
space (the server rejects spaces):

```bash
ls -l ./pool_R1.fastq.gz ./pool_R2.fastq.gz ./annotation.xlsx
```

**Confirm with the user** what will be uploaded — the reads files and that the
upload is paired-end, the annotation sheet, and that warnings are
auto-accepted — then upload. The sheet is validated and uploaded **before** the
reads, so an invalid sheet never wastes a reads upload.

```bash
flow-cli samples upload-multiplexed --reads1 ./pool_R1.fastq.gz --reads2 ./pool_R2.fastq.gz --annotation ./annotation.xlsx --json --no-progress
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
annotation validation error (exit `5`) carries `errors` (shape in
`uploading.md`) — show each row's problems and tell the user to fix the sheet. Because the annotation
is validated first, **no reads were uploaded** on a validation failure; never
claim success.

## Example 21: "Download an annotation-sheet template"

A helper for the multiplexed flow (Example 20). It changes no remote state,
so there is **no** confirmation gate. It still runs through the on-demand
flowbio CLI (the `samples annotation-template` command) so auth and base-URL
handling stay uniform. Read the `GET /annotation/<sample_type>` section of
`endpoints/samples-upload.md`. Suppose: "download the RNA-Seq annotation
template to `./template.xlsx`".

Find the sample type's identifier as in Example 19 (skip this for the
`generic` template):

```bash
flow-cli api get /v2/sample-types --json | jq -r '.[] | .identifier + " | " + .name'
```

```bash
flow-cli samples annotation-template --sample-type TYPE_IDENTIFIER -o ./template.xlsx --json --no-progress
```

On exit `0`, parse stdout `{"output": "./template.xlsx", "sample_type":
"TYPE_IDENTIFIER"}` and report where the template was written, plus that the
user should fill in one row per sample (names, file paths, metadata) before
running the multiplexed upload (Example 20). Omit `--sample-type` for the
`generic` template (base columns only). On a non-zero exit, read the stderr
JSON and the exit code (`4` = unknown sample type — re-resolve via
`/v2/sample-types`; `3` = auth; `2` = usage) — never claim success.

## Example 22: "Run the rna-seq pipeline on sample liver_rep1"

Running a pipeline is a **mutation** and **always needs the token**. The
discovery steps are reads; the run itself is one `flow-cli api post`. Read the
"Running a pipeline" section of `endpoints/pipelines.md` first — it owns the
body shape, the schema→body mapping, the confirmation gate, and the error
table.

1. **Check the token and who you are.** If this fails with a 401 (exit 3) or
   prints `NO ID`, stop and tell the user how to authenticate. If
   `can_run_pipelines` is false, stop: Flow will refuse the run.

   ```bash
   flow-cli api get /me --json | jq -r '(.id // "NO ID") + " | " + (.username // "") + " | can_run_pipelines: " + (.can_run_pipelines | tostring)'
   ```

2. **The pipeline.** List every pipeline and pick the user's by reading the
   names:

   ```bash
   flow-cli api get /pipelines --json | jq -r '.[].subcategories[].pipelines[] | .id + " | " + .name'
   ```

3. **The version.** The user named none, so take the first row, the most
   recent:

   ```bash
   flow-cli api get /pipelines/PIPELINE_ID --json | jq -r '.versions[] | .id + " | " + .name'
   ```

4. **What the version takes.** Its Nextflow versions, and each input section
   with its parameters:

   ```bash
   flow-cli api get /pipelines/versions/VERSION_ID --json | jq '{nextflow_versions, inputs: [.schema.inputs[]? | {name, params: (.params | keys)}]}'
   ```

5. **The sample.** Pick the row whose name is exactly the user's:

   ```bash
   flow-cli api get /samples/search --param name=liver_rep1 --param count=100 --json | jq -r '.samples[] | .id + " | " + .name'
   ```

Now build the body from the schema (see the mapping in `endpoints/pipelines.md`).
For a typical nf-core-style pipeline whose input is a `csv` `takes_samples`
samplesheet, you usually only need the sample id per row — the server fills
`from_sample` columns itself. Default the Nextflow version to
`nextflow_versions[0]` since the user didn't name one. If the schema has no
input that takes a sample, tell the user rather than inventing one.

**Confirm first** — show the pipeline, version (name + id), the resolved params
(sample *names*, not just ids), the Nextflow version, and the user it will run
as (the `username` from step 1), and proceed only on explicit "yes". Then:

```bash
printf '%s' '{"params":{},"data_params":{},"csv_params":{"input":{"rows":[{"sample":"SAMPLE_ID","values":{}}]}},"nextflow_version":"NEXTFLOW_VERSION"}' | flow-cli api post /pipelines/versions/VERSION_ID/run --body - --json | jq '{id, identifier, status}'
```

On success, report the execution `id`, `identifier`, initial `status`, and a
link to the run in the UI, `https://app.flow.bio/executions/<id>/`.

**Do not poll by default** — return the id and the link and stop. On `403`
(`User cannot run pipelines` or `Token not authorised for this endpoint`) report
it verbatim and stop; on `400` report the field error and fix the offending
value before re-confirming. Never claim a run started on a non-zero exit.

## Example 23: "Run the rna-seq pipeline and tell me when it finishes"

Same as Example 22 through the POST, but the user asked to be notified on
completion, so **poll** afterwards. Poll on a slow cadence — runs commonly take
hours. Check the run's status, then wait at least 60 seconds before the next
check, until `status` is `OK`, `ERROR` or `CANCELED`:

```bash
flow-cli api get /executions/EXECUTION_ID --param include=status --param include=finished --json | jq -r '.status + " | finished: " + (.finished | tostring)'
```

Until then `status` is `""` or `-` (see "Where a run is in its life" in
`endpoints/executions.md`). On `OK`, report success (optionally tail the log
with `--param log=<offset>`). On `ERROR`, fetch and surface `stderr` / `log` /
the failing `process_executions` entry — never report success on a non-`OK`
terminal status.

## Example 24: "Set the cell line of sample liver_rep1 to HepG2"

A record edit. Read `/v2/reference/samples` first; it says which attributes
apply to the sample's type and how the edit reports a refused value.

1. **The sample.** More than one match? Ask the user which.

   ```bash
   flow-cli api get /samples/search --param name=liver_rep1 --param count=100 --json | jq -r '.samples[] | .id + " | " + .name + " | " + .sample_type.identifier'
   ```

2. **The attribute.** List the attributes this sample's type can carry, using
   the type step 1 printed, and match the user's "cell line" to a row's name;
   the description tells similar attributes apart:

   ```bash
   flow-cli api get /v2/metadata-attributes --param sample_type=SAMPLE_TYPE --json | jq -r '.[] | .identifier + " | " + .name + " | " + (.description // "") + " | has_options: " + (.has_options | tostring)'
   ```

3. **The value.** The attribute has options, so check the value is one of them.
   The filter matches substrings, so check one row is exactly `HepG2` (not
   `HepG2-C3A`). None is, and the attribute has no `allow_user_terms`? Tell the
   user.

   ```bash
   flow-cli api get /v2/metadata-attributes/IDENTIFIER/options --param value=HepG2 --param page_size=100 --json | jq -r '.items[].value'
   ```

4. **Confirm with the user**: sample liver_rep1, cell line → HepG2. Then send
   only that attribute; everything else on the sample keeps its value. One line
   of JSON in single quotes; write an apostrophe in a value as `\u0027`
   (`"Martin\u0027s samples"`), since a literal `'` would end the shell's quoting.

   ```bash
   printf '%s' '{"metadata": {"IDENTIFIER": {"value": "HepG2"}}}' | flow-cli api patch /v2/samples/SAMPLE_ID --body - --json | jq '{id, name, value: .metadata.IDENTIFIER}'
   ```

Report the value from the response. A 422 lists each problem with its
`pointer`: `/metadata/<identifier>` is a value the attribute refuses (for
example, one not among its options), or, with code `unknown_attribute`, an
identifier this instance does not have. Report the `detail`; never claim
success.

## Example 25: "Create a project called Liver Atlas"

A record creation. Read `/v2/reference/projects` first. **Confirm with the
user**: project "Liver Atlas", description "Bulk RNA-Seq of liver tissue",
private (say public only if the user asked for it). Then:

```bash
printf '%s' '{"name": "Liver Atlas", "description": "Bulk RNA-Seq of liver tissue"}' | flow-cli api post /v2/projects --body - --json | jq '{id, name}'
```

Report the new project's id. A 422 pointing at `/name` means the user already
has a project with that name: report it and ask, rather than picking another
name. To make the project public, add `"private": false` to the body, and only
when the user asked for it; an existing project's visibility is changed only in
the Flow web app.
