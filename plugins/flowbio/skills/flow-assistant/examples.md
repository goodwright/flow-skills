# Worked examples — reading & querying

End-to-end recipes for read-only questions. For per-endpoint parameter and
response details see `endpoints/<name>.md`; for upload and pipeline-run recipes
see `examples-write.md`.

Every command follows SKILL.md's rules: one line, no `VAR=…` assignments, and
`flow-cli` for every Flow call (the file download in Example 7 is the one
`curl`). Words in capitals (`SAMPLE_ID`, `ORGANISM_ID`) are placeholders:
replace each with the value a previous command printed, never with a guess.

## Authentication and these recipes

Every recipe below works in two modes:

- **Unauthenticated** (no `~/.config/flow/api-token` file): returns
  public results only.
- **Authenticated** (token file present): the flowbio CLI attaches the
  caller's token automatically, and the same recipes return a broader set
  including the caller's owned and shared resources.

No flag changes between the two modes — the CLI reads the token file itself
if it is there. For a caller-scoped recipe (e.g. `owned=true`), verify auth via
`/me` first (Example 14); if there is no valid token, tell the user how to
authenticate ("Authentication" in SKILL.md) rather than silently reporting the
misleading anonymous result.

## Example 1: "What pipelines does Flow offer?"

The catalog is unpaginated, so a single GET is enough.

```bash
flow-cli api get /pipelines --json | jq -r '.[] | .name as $category | .subcategories[].pipelines[] | $category + " | " + .name'
```

Report a grouped summary by category with pipeline names.

## Example 2: "What's the latest version of the rna-seq pipeline?"

You run a *version*, not a pipeline, and `/pipelines` lists pipelines only.
Find the pipeline's id there, then read its versions from `GET /pipelines/<id>`
(see `endpoints/pipelines.md`).

List every pipeline and pick the user's by reading the names:

```bash
flow-cli api get /pipelines --json | jq -r '.[].subcategories[].pipelines[] | .id + " | " + .name'
```

Then list its versions, most recent first:

```bash
flow-cli api get /pipelines/PIPELINE_ID --json | jq -r '.versions[] | .id + " | " + .name'
```

The first row is the latest version. Report its name, and its id if the user
wants to run it.

## Example 3: "Find samples whose name contains 'liver'"

`name` is a substring match on the sample's name, so it suits a word the user
expects to see in names. It is the wrong tool for an assay, an organism or a
tissue: those live in the sample type, the organism and the metadata, and are
found by their identifiers (SKILL.md Step 4, and Examples 16 and 17).

```bash
flow-cli api get /samples/search --param name=liver --param count=100 --json | jq -r '"total: " + (.count|tostring), (.samples[] | .id + " | " + .name + " | " + (.project_name // "-"))'
```

If the total is above 100, walk every page with the loop in SKILL.md Shape B
before listing them all. For one sample's full record, see Example 9.

## Example 4: "List the projects I can see"

"How many" is one request (Shape A):

```bash
flow-cli api get /projects/search --param count=1 --json | jq -r '.count'
```

"List them" needs every page (Shape B), because one request returns at most 100:

```bash
for p in $(seq 1 $(flow-cli api get /projects/search --param count=1 --json | jq -r '((.count+99)/100|floor)')); do flow-cli api get /projects/search --param count=100 --param page=$p --json | jq -r '.projects[] | .id + " | " + .name + " | samples: " + (.sample_count|tostring)'; done
```

Say how many pages you walked and the total.

## Example 5: "What executions has sample liver_rep1 been used in?"

Resolve the name to an id, then list that sample's executions.

```bash
flow-cli api get /samples/search --param name=liver_rep1 --param count=100 --json | jq -r '.samples[] | .id + " | " + .name + " | " + (.project_name // "-")'
```

`name` is a substring match: if more than one row comes back, pick the exact
name or ask the user which they mean. Then:

```bash
flow-cli api get /samples/SAMPLE_ID/executions --param count=100 --json | jq -r '"total: " + (.count|tostring), (.executions[] | .id + " | " + .identifier + " | " + .pipeline_name + " | " + .status)'
```

If the second call reports a 404 (`status_code` 404 in the error envelope),
the sample id is wrong OR the sample is private (a private sample inside a
public project is listed by `/samples/search` but its sub-resources still 404
for anonymous callers — flag this to the user).

## Example 6: "What files are in sample liver_rep1?"

This question is the union endpoint — raw inputs **plus** every
pipeline-produced output traced back to the sample. Don't substitute
`/samples/<id>` and read `filesets[].data`; that returns only the raw
inputs and silently undercounts processed samples (see "raw input
files vs sample-related data" in `endpoints/samples.md`). Resolve the name to
`SAMPLE_ID` as in Example 5, then:

```bash
flow-cli api get /samples/SAMPLE_ID/data --param count=100 --json | jq -r '"total: " + (.count|tostring), (.data[] | .id + " | " + .filename + " | " + (.size|tostring) + " | " + (.pipeline_name // "raw input"))'
```

A processed sample can have hundreds of files: if the total is above 100, walk
every page with the loop in SKILL.md Shape B. A row with no `pipeline_name` is a
raw input; any other is a pipeline output. Each `id`/`filename` pair is the
input to the download endpoint (Example 7). Don't surface `absolute_path` to the
user — it's a Flow-internal path.

## Example 7: "Download a public file"

Chain: discover sample → list its data (Example 6) → download by
`id`/`filename`. A download is raw bytes, so it uses `curl` (not `api get`,
which returns text). Before downloading anything large, confirm with the user
— the file size is in the previous response under `.data[].size` (bytes).

```bash
curl -s --fail-with-body -o FILENAME https://app.flow.bio/api/downloads/DATA_ID/FILENAME
```

Notes:

- `DATA_ID` is a **Data id**, not a bulk-download job id, even
  though the URL is under `/downloads/`.
- The trailing path segment must equal `data.filename` exactly — copy it from
  the `/samples/<id>/data` response.
- `--fail-with-body` makes a refused download exit non-zero instead of `0`.
  The `-o` file then holds the server's error text, not the file: report the
  text and delete the file. Never report a download as done on a non-zero exit.
- 410 with `Data <id> (<filename>) was deleted on <date>` means the
  file's content was deleted under the retention policy. Say so, with the
  date; there is no other copy to fetch.
- 404 with empty body means: id wrong, file not ready, filename mismatch,
  or the data is not anonymous-readable. The endpoint does not return
  JSON for errors.
- For **private** data, attach the token to the curl:
  `-H "Authorization: Bearer $(< ~/.config/flow/api-token)"` (token discipline,
  `safety.md`). Omit it for public data.
- Use `?direct=yes` if the user wants the file served inline (e.g. for a
  text or image preview in a browser); leave it off for "save to disk"
  semantics.

## Example 8: "Show me the first chunk of a text file"

```bash
flow-cli api get /data/DATA_ID/contents --json | jq -r '.contents[:2000], "has_more: " + (.has_more|tostring)'
```

The endpoint returns up to 10 KB per call. To read the next chunk, pass
`--param position=1` (chunk **index**, not byte offset); then `--param
position=2`, and so on, until `has_more` is `false`. If the read fails with a
`status_code` 400 and message `Data is binary` or `Data is directory`, fall
back to the download endpoint (Example 7). For full-file content, the download
endpoint is faster than chunking through `/contents`.

## Example 9: "Tell me about sample liver_rep1"

Single-sample drill-down. Use the detail endpoint
(`endpoints/samples.md` → `/samples/<id>`), not the list
endpoint — only the detail endpoint exposes the full metadata bag. Resolve the
name to `SAMPLE_ID` as in Example 5, then:

```bash
flow-cli api get /samples/SAMPLE_ID --json | jq '{id, name, sample_type, organism: .organism.name, project: .project.name, pubmed, metadata: [.metadata | to_entries[] | {attribute: .value.attribute_name, value: .value.value}], raw_input_count: ([.filesets[].data[]] | length)}'
```

Project the metadata as a small list of `{attribute, value}` pairs (the
underlying object is keyed by attribute identifier and carries
`attribute_description`, `is_list`, `url_pattern`, `annotation` per entry —
ignore those unless the user asks). Report the metadata in full when
that's the user's question; the list endpoint cannot answer it
correctly. If the read fails with `status_code` 404, the id is
wrong or both the sample and its parent project are private.

The count above is **raw input files only** — `.filesets[]` does not
include pipeline outputs. If the user asks "how many files does this
sample have" without qualifier, that's the union question — answer
from `/samples/<id>/data` (Example 6) instead, and use this endpoint
only for the metadata projection.

## Example 10: "Tell me about project Liver Atlas"

Find its id. `name` is a substring match, so pick the row whose name is exactly
the user's ("Liver Atlas" also matches "Public Liver Atlas"):

```bash
flow-cli api get /projects/search --param "name=Liver Atlas" --param count=100 --json | jq -r '.projects[] | .id + " | " + .name'
```

Then fetch the detail record:

```bash
flow-cli api get /projects/PROJECT_ID --json | jq '{id, name, description, private, owner: .owner.name, papers: [.papers[] | {year, title, journal}]}'
```

The detail view does not include `sample_count` / `execution_count` —
read them from the `/projects/search` row if the user asks for those numbers.

## Example 11: "Tell me about file counts.tsv"

Read `GET /v2/reference/data` first: it lists every field of the record and how
to find a file by name. Then, with the file's id:

```bash
flow-cli api get /v2/data/DATA_ID --json | jq '{id, filename, filetype, size, is_directory, data_type, deletion_scheduled_for, file_deleted_at}'
```

Don't surface `absolute_path` — it's a Flow-internal path.
For text content use Example 8; for the file bytes use Example 7.

## Example 12: "Find the executions I ran yesterday"

`owned=true` needs a working token, so check it first:

```bash
flow-cli api get /me --json | jq -r '.id // "NO ID"'
```

If that fails with a 401 (exit 3) or prints `NO ID`, stop and give the
authentication guidance (Example 14). `created_gt` and `created_lt` take **Unix
timestamp integers**, not dates, so work out the start of yesterday and of
today. Each line works on Linux and macOS:

```bash
date -d 'yesterday 00:00' +%s 2>/dev/null || date -v-1d -v0H -v0M -v0S +%s
```

```bash
date -d 'today 00:00' +%s 2>/dev/null || date -v0H -v0M -v0S +%s
```

Then put the two numbers in place of `START` and `END`:

```bash
flow-cli api get /executions/search --param owned=true --param created_gt=START --param created_lt=END --param count=100 --json | jq -r '"total: " + (.count|tostring), (.executions[] | .id + " | " + .identifier + " | " + .pipeline_name + " | " + .status)'
```

Passing an ISO-8601 date to either is a 400 naming the field.

## Example 13 (negative): "Delete sample 42"

Decline. Sample deletion isn't in the skill's allowlist (see "Safety" in
SKILL.md). The Safety principle refuses any operation not explicitly
documented, regardless of HTTP verb or auth state.

## Example 14: "What samples do I own?"

**Always verify authentication first via `/me`.** A missing or invalid token
makes `/me` return **401** (`api get` exit 3) — but `/samples/search?owned=true`
does NOT error: it silently treats you as anonymous and filters to
`owner=NULL`, returning a plausible but wrong count. So gate the `owned=true`
query on a successful `/me`:

```bash
flow-cli api get /me --json | jq -r '.id // "NO ID"'
```

If that fails with a 401 (exit 3) or prints `NO ID`, tell the user their token
is missing, expired, or invalid, and how to authenticate ("Authentication" in
SKILL.md) — don't fall through to a misleading `owned=true` query. Otherwise:

```bash
flow-cli api get /samples/search --param owned=true --param count=1 --json | jq -r '.count'
```

To list them, walk every page with the loop in SKILL.md Shape B, adding
`--param owned=true` to both calls.

If the question involves the user's groups ("samples in groups I belong to"),
`/me` lists them:

```bash
flow-cli api get /me --json | jq -r '.memberships[] | .slug + " | " + .name'
```

## Example 15: "What filters does this instance support?"

Sample types and every metadata attribute are filters on `/samples/search`.
List them all with the discovery command in SKILL.md Step 4:

```bash
(  flow-cli api get /v2/sample-types --json | jq -r '.[] | "TYPE | " + .identifier + " | " + .name';  flow-cli api get /v2/metadata-attributes --json | jq -r '.[] | "ATTR | " + .identifier + " | " + .name + " | " + .description'  )
```

`TYPE` rows filter with `--param sample_types=<identifier>`, `ATTR` rows with
`--param <identifier>=<value>`. Report the identifiers and names. If the user then asks about a specific
concept ("filter by tissue"), match their word against the `name` column and
use that row's `identifier`. If no row matches, tell the user honestly — don't
guess. The API does not reject unknown filter params, so this check is the only
safeguard.

## Example 16: "Find human samples"

Two calls: find the organism's id, then filter samples by it. List every
organism and pick the user's by reading the rows; never filter the list for the
user's word, which may be spelled differently here ("Homo sapiens"):

```bash
flow-cli api get /organisms --json | jq -r '.[] | .id + " | " + .name + " | " + .latin_name'
```

```bash
flow-cli api get /samples/search --param organism=ORGANISM_ID --param count=1 --json | jq -r '.count'
```

If no row matches the user's organism, say so and list the organisms the
instance has. Never send `organism=human` or an empty `organism=`: the API
ignores the filter and returns every sample.

## Example 17: "Find samples where the source is liver"

1. **Find the attribute.** List every attribute (Example 15) and match the
   user's word against the `name` column; use that row's `identifier` below. If
   no row matches, tell the user this instance has no such attribute, list the
   ones it has, and stop.
2. **Learn its values.**
   - If the row has `has_options` true, its options are the values it may take.
     The list is paged, 25 to a page unless you ask for more, so ask for 100
     and read the total:

     ```bash
     flow-cli api get /v2/metadata-attributes/IDENTIFIER/options --param page_size=100 --json | jq -r '"total: " + (.count|tostring), .items[].value'
     ```

     If the total is above 100, walk `--param page=2`, `3` and so on, or narrow
     it with `--param value=<part of the user's word>` and read every row. An
     empty narrowed list is not a "no match": the instance may word the value
     differently ("cortex" for "brain"), so walk the pages before concluding.

   - Otherwise the values are free text. Collect the ones in use from every
     sample with the loop in SKILL.md Shape B, with the attribute's identifier
     in the `jq` program (`.metadata.IDENTIFIER.value // empty`). A handful of
     records is not enough: a value absent from them is not absent from Flow.
3. **Filter.** `--param "IDENTIFIER=VALUE"` matches a substring of the value:

   ```bash
   flow-cli api get /samples/search --param "IDENTIFIER=VALUE" --param count=1 --json | jq -r '.count'
   ```

   Check that the count dropped from the unfiltered total: an identifier this
   instance does not have is ignored, and the unfiltered count comes back.

If the user's term matches none of the values (every page of them), say so and
show them the values there are, rather than filtering on a near miss.
