# Worked examples — reading & querying

End-to-end recipes for read-only questions. For per-endpoint parameter and
response details see `endpoints/<name>.md`; for upload and pipeline-run recipes
see `examples-write.md`.

## Authentication and these recipes

Every recipe below works in two modes:

- **Unauthenticated** (no `~/.config/flow/api-token` file): returns
  public results only.
- **Authenticated** (token file present): the flowbio CLI attaches the
  caller's token automatically, and the same recipes return a broader set
  including the caller's owned and shared resources.

No flag changes between the two modes — the CLI reads the token file itself
if it is there. For a caller-scoped recipe (e.g. `owned=true`), verify auth via
`/me` first (it returns 401 when unauthenticated); if there is no valid token,
tell the user how to authenticate (SKILL.md §3) rather than silently reporting
the misleading anonymous result.

## Example 1: "What pipelines does Flow offer?"

The catalog is unpaginated, so a single GET is enough. Project to category
names and pipeline counts.

```bash
flowbio api get /pipelines --json | \
  jq '[.[] | {category: .name, pipelines: [.subcategories[].pipelines[].name]}]'
```

Report a grouped summary by category with pipeline names.

## Example 2: "Find the latest version of the rna-seq pipeline"

The public `/pipelines` endpoint exposes pipeline names and ids, but it
does **not** expose per-pipeline version lists — the per-pipeline fields
are limited to `id`, `name`, `description`, `execution_count`, `is_nfcore`,
`prepares_genome`. Version listing requires authenticated endpoints, which
are out of scope for v1.

Identify the rna-seq pipeline from the catalog:

```bash
flowbio api get /pipelines --json | \
  jq '[.. | objects | select(.name? | test("rna.?seq"; "i")) | select(.id?)] | .[] | {id, name, description}'
```

Report something like: "I found the rna-seq pipeline (id `<id>`,
description `<desc>`). The public catalog doesn't expose per-pipeline
version lists, so I can't tell you the latest version from this endpoint.
Version listing requires authenticated endpoints, which are out of scope
for this skill."

## Example 3: "Find public samples mentioning RNA-seq"

`/samples/search` is field-scoped — there is no single cross-field
substring. Use `name` for a substring match on sample name (the most
common intent). If the user wants to filter by organism, a separate
discovery step is needed to find the organism pk; `name=rna-seq` is the
practical fallback and usually sufficient.

```bash
flowbio api get /samples/search \
  --param name=rna-seq \
  --param count=20 --json | \
  jq '{total: .count, page: .page, samples: [.samples[] | {id, name, organism: .organism.name, sample_type: .sample_type.name, project: .project_name}]}'
```

Report total matches, page shown, and a compact list. If the user wanted
organism-specific filtering (e.g. "all human RNA-seq samples"), use the
two-step recipe in Example 16: resolve the organism name to its `id` via
`GET /organisms` first, then chain into `/samples/search?organism=<id>`.
For simple name-based searches `name=rna-seq` (this recipe) is the
correct starting point.

For a single-sample drill-down (full record, full metadata bag), use
the detail endpoint instead — see Example 9 below.

## Example 4: "List public projects"

```bash
flowbio api get /projects/search \
  --param count=100 --json | \
  jq '{total: .count, page: .page, projects: [.projects[] | {id, name, samples: .sample_count, executions: .execution_count}]}'
```

If `total` exceeds 100, paginate by passing `--param page=2`, `--param page=3`,
etc., and roll up before reporting. For most user questions the first page plus
the total is sufficient; only paginate when the user actually needs the long
tail.

## Example 5: "What executions has sample 12345 been used in?"

Two steps. First confirm the sample is reachable via the search endpoint
(useful when the user gives a name rather than an id), then list its
executions.

```bash
flowbio api get /samples/search \
  --param name=12345 --json | \
  jq '.samples[] | {id, name, project_name}'
```

```bash
flowbio api get /samples/12345/executions \
  --param count=50 --json | \
  jq '{total: .count, page: .page, executions: [.executions[] | {id, identifier, pipeline_name, pipeline_version, status, created}]}'
```

If the second call reports a 404 (`status_code` 404 in the error envelope),
the sample id is wrong OR the sample is private (a private sample inside a
public project is listed by `/samples/search` but its sub-resources still 404
for anonymous callers — flag this to the user).

## Example 6: "What files are in sample 12345?"

This question is the union endpoint — raw inputs **plus** every
pipeline-produced output traced back to the sample. Don't substitute
`/samples/<id>` and read `filesets[].data`; that returns only the raw
inputs and silently undercounts processed samples (see "raw input
files vs sample-related data" in `endpoints/samples.md`).

```bash
flowbio api get /samples/12345/data \
  --param count=100 --json | \
  jq '{total: .count, files: [.data[] | {id, filename, size, pipeline_name}]}'
```

`pipeline_name == null` in a row means a raw input; non-null means a
pipeline output. Each `id`/`filename` pair is the input to the
download endpoint (Example 7). Don't surface `absolute_path` to the
user — it's a Flow-internal path.

## Example 7: "Download a public file"

Chain: discover sample → list its data → download by `id`/`filename`. A
download is raw bytes, so it uses `curl` (not `api get`, which returns text).
Before downloading anything large, confirm with the user — the file size
is in the previous response under `.data[].size` (bytes).

```bash
curl -s -A "flow-ai/0.11.0" -o sample.fastq.gz \
  "${FLOW_API_URL:-https://app.flow.bio/api}/downloads/67890/sample.fastq.gz"
```

Notes:

- The id (`67890`) is a **Data id**, not a bulk-download job id, even
  though the URL is under `/downloads/`.
- The trailing path segment (`sample.fastq.gz`) must equal `data.filename`
  exactly — copy it from the `/samples/<id>/data` response.
- 404 with empty body means: id wrong, file not ready, filename mismatch,
  or the data is not anonymous-readable. The endpoint does not return
  JSON for errors.
- For **private** data, attach the token to the curl:
  `-H "Authorization: Bearer $(< ~/.config/flow/api-token)"` (token discipline,
  `safety.md`). Omit it for public data.
- Use `?direct=yes` if the user wants the file served inline (e.g. for a
  text or image preview in a browser); leave it off for "save to disk"
  semantics.

## Example 8: "Show me the first chunk of a public text file"

```bash
flowbio api get /data/67890/contents --json | \
  jq '{has_more, contents: (.contents[:2000])}'
```

The endpoint returns up to 10 KB per call. To read the next chunk, pass
`--param position=1` (chunk **index**, not byte offset); then `--param
position=2`, and so on, until `has_more` is `false`. If the read fails with a
`status_code` 400 and message `Data is binary` or `Data is directory`, fall
back to the download endpoint (Example 7). For full-file content, the download
endpoint is faster than chunking through `/contents`.

## Example 9: "Tell me about sample 12345"

Single-sample drill-down. Use the detail endpoint
(`endpoints/samples.md` → `/samples/<id>`), not the list
endpoint — only the detail endpoint exposes the full metadata bag. If
the user gave a name rather than an id, discover the id first via
`/samples/search?name=<name>` (Example 3).

```bash
flowbio api get /samples/12345 --json | \
  jq '{id, name, sample_type, organism: .organism.name, project: .project.name, pubmed,
       metadata: [.metadata | to_entries[] | {attribute: .value.attribute_name, value: .value.value}],
       raw_input_count: ([.filesets[].data[]] | length)}'
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

## Example 10: "Tell me about project 4567"

Discover by name first if needed via `/projects/search?name=…`
(Example 4), then fetch the detail record:

```bash
flowbio api get /projects/4567 --json | \
  jq '{id, name, description, owner: .owner.name, papers: [.papers[] | {year, title, journal}]}'
```

The detail view does not include `sample_count` / `execution_count` —
fall back to `/projects/search?name=<name>` if the user asks for
those numbers.

## Example 11: "Tell me about file 67890"

```bash
flowbio api get /data/67890 --json | \
  jq '{id, filename, filetype, size, is_binary, is_directory,
       sample: .sample.name, project: .project.name, fileset: .fileset.name,
       pipeline: .execution.pipeline_name, process: .execution.process_name}'
```

Don't surface `absolute_path` — it's a Flow-internal path. If the user
asks for the producing process's bash command, it's available at
`.execution.process_command`; surface it explicitly only when asked.
For text content use Example 8; for the file bytes use Example 7.

## Example 12: "Find the executions I ran yesterday"

Use `/executions/search` with `owned=true` (requires auth) and a Unix
timestamp lower bound. Compute yesterday's start time as a Unix timestamp
first:

```bash
YESTERDAY=$(date -d "yesterday 00:00:00" +%s 2>/dev/null || date -v-1d -v0H -v0M -v0S +%s)

flowbio api get /executions/search \
  --param owned=true \
  --param created_gt=$YESTERDAY \
  --param count=50 --json | \
  jq '{total: .count, executions: [.executions[] | {id, identifier, pipeline_name, status, created}]}'
```

Notes:
- `date -d` is GNU (Linux/CI); `date -v` is BSD (macOS). The compound
  command tries GNU first and falls back to BSD.
- `created_gt` takes a **Unix timestamp integer** — passing an ISO-8601
  string causes HTTP 500.
- `owned=true` requires authentication. Always verify auth via `/me`
  first (see Example 14 — a missing/invalid token makes `/me` return 401).
  The search endpoint itself does NOT error without auth — it silently filters
  to `owner=NULL` and returns a plausible-but-wrong count.
  Same precondition applies to filtering executions by `owned=true`.

## Example 13 (negative): "Delete sample 42"

Decline. Sample deletion isn't in the skill's allowlist (see SKILL.md
§1). The Safety principle refuses any operation not explicitly
documented, regardless of HTTP verb or auth state.

## Example 14: "What samples do I own?"

**Always verify authentication first via `/me`.** A missing or invalid token
makes `/me` return **401** (`api get` exit 3) — but `/samples/search?owned=true`
does NOT error: it silently treats you as anonymous and filters to
`owner=NULL`, returning a plausible but wrong count. So gate the `owned=true`
query on a successful `/me`.

```bash
# Step 1: verify the token works — /me 401s (exit 3) when it is missing/invalid.
if ! ME=$(flowbio api get /me --json 2>/dev/null) \
   || [ -z "$(printf '%s' "$ME" | jq -r '.id // empty')" ]; then
  echo "Not authenticated: /me failed. Token missing, expired, or invalid."
  exit 1
fi

# Step 2: only now is it safe to use owned=true
flowbio api get /samples/search \
  --param owned=true --param count=20 --json | \
  jq '{total: .count, samples: [.samples[] | {id, name, project: .project_name}]}'
```

If `/me` fails (401) or returns no `id`, tell the user their token is missing,
expired, or invalid, and how to authenticate (SKILL.md §3) — don't fall
through to a misleading `owned=true` query.

If the user's intent involves group membership ("samples in groups
I belong to") or cross-resource linkage, `$ME` from the precheck
already has what you need:

```bash
echo "$ME" | jq '{id, name, memberships: [.memberships[].slug]}'
```

Then use `$MY_ID` as appropriate for the question. Note: `/me` returns 401
on a missing/invalid token, but search endpoints like `/samples/search`
silently treat a bad token as anonymous (no 401) and return a misleading
`owned=true` count — which is exactly why the `/me` precheck is required.

## Example 15: "What filters does this instance support?"

`GET /samples/metadata` is the canonical answer. Project to the
useful fields:

```bash
flowbio api get /samples/metadata --json | \
  jq '[.[] | {identifier, name, description, has_options, allow_user_terms}]'
```

Report the available identifiers to the user. If the user then asks
about a specific concept ("filter by tissue"), check whether their
term is in the response's `identifier` or `name` fields before
issuing the filter on `/samples/search`. If it isn't, tell the user
honestly — don't guess. The API does not currently reject unknown
filter params, so this manual check is the only safeguard.

## Example 16: "Find human samples"

Two-call recipe: resolve organism name → pk, then filter samples.

```bash
# Resolve "human" to an organism pk
HUMAN_ID=$(flowbio api get /organisms --json | \
  jq -r '.[] | select(.name | ascii_downcase == "human") | .id')

# Filter samples by that pk
flowbio api get /samples/search \
  --param organism=$HUMAN_ID --param count=20 --json | \
  jq '{total: .count, samples: [.samples[] | {id, name, sample_type}]}'
```

If `$HUMAN_ID` is empty, tell the user there's no organism named
"human" on this instance — don't fall back to a string filter on
`organism=human` (silently no-ops). The `organism` param only
accepts pks today, hence the resolve-first pattern.

## Example 17: "Filter by a metadata attribute"

Three-call recipe demonstrating the discovery pattern for
metadata-scoped questions. Suppose the user asks "find samples
where source is brain":

```bash
# Step 1: discover whether 'source' exists on this instance
flowbio api get /samples/metadata --json | \
  jq '.[] | select(.identifier == "source")'
# If no row: tell the user this instance has no 'source' attribute,
# list the available identifiers, and stop.

# Step 2: inspect a small sample of records to learn the value
# vocabulary (no values-discovery endpoint today; this is the workaround)
flowbio api get /samples/search \
  --param count=10 --json | \
  jq '[.samples[] | .metadata.source.value] | unique'
# Tells you the actual values present — e.g. ["Temporal Cortex",
# "Hippocampus", "HEK293", null]. If the user's term "brain" doesn't
# match any of them literally, surface this to them; substring
# search may still under-match.

# Step 3: filter with a well-chosen substring
flowbio api get /samples/search \
  --param source=Cortex --param count=20 --json | \
  jq '{total: .count, samples: [.samples[] | {id, name, source: .metadata.source.value}]}'
```

The discovery overhead (steps 1 and 2) feels expensive but
eliminates the silent-no-op class of bug and lets the agent set
correct expectations with the user instead of guessing.


## Example 18: "Which public samples have outputs from pipeline X, version Y?"

For example "public CLIP samples processed with CLIP-Seq v1.6 or v1.7". Use the
public-only prefix (see "Public-only reads" in `SKILL.md`) for every read below.

**Narrow the samples before you touch any files.** Every `flowbio` call starts a
new Python process, and output files can be large, so fetching "everything"
can take hours and swamp the user's computer. Decide which samples you need
from their metadata first (drop controls, off-topic samples, other organisms),
then fetch files for those only. Run at most 4 calls in parallel.

**Link files to samples by id, never by filename or sample name.** Output
filenames do not reliably match sample names: a sample's own data list can hold
a file named after a different sample. Sample names are not unique either.

```bash
# Step 1: the pipeline id
flowbio api get /pipelines --json | \
  jq -r '.[].subcategories[].pipelines[] | .id + " | " + .name'

# Step 2: every successful run, with its version (Shape B pagination).
# Keep the versions the user asked for.
flowbio api get /executions/search --param pipeline=<id> --param status=OK \
  --param count=100 --param page=<p> --json | \
  jq -r '.executions[] | [.id, .pipeline_version] | @tsv'

# Step 3: sample metadata (Shape B), then choose the samples you need
flowbio api get /samples/search --param sample_types=<type> \
  --param full_metadata=true --param count=100 --param page=<p> --json

# Step 4: for each chosen sample, its files of one kind. The list is scoped by
# sample id, so membership is reliable even when filenames are not. `filter`
# is a substring on the filename (and on sample, pipeline and owner names), so
# make it specific.
flowbio api get /samples/<sample id>/data --param filter=<filename fragment> \
  --param count=100 --json | jq -r '.data[] | .id + " " + .filename'

# Step 5: only when a sample has more than one matching file, find each file's run
flowbio api get /data/<data id> --json | jq -r '.execution.id'
```

Then keep only files whose run is one of those kept in step 2. If more than one
remains for a sample, use the newest run. Outputs of multiplexed runs are not
attached to any sample, so they never appear in step 4; if a chosen sample has
no files, say so rather than matching files to it by name.

Fetch small files first (logs, summaries) and use them to narrow further before
fetching large ones. Download a large file, reduce it to what you need, and
delete it before fetching the next rather than keeping them all.

For a run's reference files (genome, annotation, GTFs), take them from the run
itself, ~2 KB per call:

```bash
flowbio api get /executions/<run id> --param include=data_params --json
```

A reference file a run lists may since have been deleted (`/data/<id>` returns
404, even logged in). See `endpoints/executions.md` for what to do.
