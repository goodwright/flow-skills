# Worked examples

End-to-end recipes covering the skill's endpoints. For per-endpoint
parameter and response details, see `endpoints/<name>.md`.

## Authentication and these recipes

Every recipe below works in two modes:

- **Unauthenticated** (no `~/.config/flow/api-token` file): returns
  public results only. The skill omits the `Authorization` header.
- **Authenticated** (token file present): the skill attaches
  `-H "Authorization: Bearer $(< ~/.config/flow/api-token)"` on every
  request, and the same recipes return a broader set including the
  caller's owned and shared resources.

Recipe text below shows the unauthenticated invocations for clarity.
With a token file in place, prepend the `-H "Authorization: Bearer …"`
flag to every `curl` command (no other change).

## Example 1: "What pipelines does Flow offer?"

The catalog is unpaginated, so a single GET is enough. Project to category
names and pipeline counts.

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/pipelines" | \
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
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/pipelines" | \
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
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "name=rna-seq" \
  --data-urlencode "count=20" | \
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
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/projects/search" \
  --data-urlencode "count=100" | \
  jq '{total: .count, page: .page, projects: [.projects[] | {id, name, samples: .sample_count, executions: .execution_count}]}'
```

If `total` exceeds 100, paginate by passing `page=2`, `page=3`, etc., and
roll up before reporting. For most user questions the first page plus the
total is sufficient; only paginate when the user actually needs the long
tail.

## Example 5: "What executions has sample 12345 been used in?"

Two steps. First confirm the sample is reachable via the search endpoint
(useful when the user gives a name rather than an id), then list its
executions.

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "name=12345" | \
  jq '.samples[] | {id, name, project_name}'
```

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/12345/executions" \
  --data-urlencode "count=50" | \
  jq '{total: .count, page: .page, executions: [.executions[] | {id, identifier, pipeline_name, pipeline_version, status, created}]}'
```

If the second call returns 404, the sample id is wrong OR the sample is
private (a private sample inside a public project is listed by
`/samples/search` but its sub-resources still 404 for anonymous callers —
flag this to the user).

## Example 6: "What files are in sample 12345?"

This question is the union endpoint — raw inputs **plus** every
pipeline-produced output traced back to the sample. Don't substitute
`/samples/<id>` and read `filesets[].data`; that returns only the raw
inputs and silently undercounts processed samples (see "raw input
files vs sample-related data" in `endpoints/samples.md`).

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/12345/data" \
  --data-urlencode "count=100" | \
  jq '{total: .count, files: [.data[] | {id, filename, size, pipeline_name}]}'
```

`pipeline_name == null` in a row means a raw input; non-null means a
pipeline output. Each `id`/`filename` pair is the input to the
download endpoint (Example 7). Don't surface `absolute_path` to the
user — it's a Flow-internal path.

## Example 7: "Download a public file"

Chain: discover sample → list its data → download by `id`/`filename`.
Before downloading anything large, confirm with the user — the file size
is in the previous response under `.data[].size` (bytes).

```bash
curl -s -A "flow-ai/0.4.0" -o sample.fastq.gz \
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
- Use `?direct=yes` if the user wants the file served inline (e.g. for a
  text or image preview in a browser); leave it off for "save to disk"
  semantics.

## Example 8: "Show me the first chunk of a public text file"

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/data/67890/contents" | \
  jq '{has_more, contents: (.contents[:2000])}'
```

The endpoint returns up to 10 KB per call. To read the next chunk, pass
`position=1` (chunk **index**, not byte offset); then `position=2`, and
so on, until `has_more` is `false`. If the response is
`400 {"error": "Data is binary"}` or `400 {"error": "Data is directory"}`,
fall back to the download endpoint (Example 7). For full-file content, the
download endpoint is faster than chunking through `/contents`.

## Example 9: "Tell me about sample 12345"

Single-sample drill-down. Use the detail endpoint
(`endpoints/samples.md` → `/samples/<id>`), not the list
endpoint — only the detail endpoint exposes the full metadata bag. If
the user gave a name rather than an id, discover the id first via
`/samples/search?name=<name>` (Example 3).

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/12345" | \
  jq '{id, name, sample_type, organism: .organism.name, project: .project.name, pubmed,
       metadata: [.metadata | to_entries[] | {attribute: .value.attribute_name, value: .value.value}],
       raw_input_count: ([.filesets[].data[]] | length)}'
```

Project the metadata as a small list of `{attribute, value}` pairs (the
underlying object is keyed by attribute identifier and carries
`attribute_description`, `is_list`, `url_pattern`, `annotation` per entry —
ignore those unless the user asks). Report the metadata in full when
that's the user's question; the list endpoint cannot answer it
correctly. If the response is `{"error": "Not found"}` (404), the id is
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
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/projects/4567" | \
  jq '{id, name, description, owner: .owner.name, papers: [.papers[] | {year, title, journal}]}'
```

The detail view does not include `sample_count` / `execution_count` —
fall back to `/projects/search?name=<name>` if the user asks for
those numbers.

## Example 11: "Tell me about file 67890"

```bash
curl -s -A "flow-ai/0.4.0" --get "${FLOW_API_URL:-https://app.flow.bio/api}/data/67890" | \
  jq '{id, filename, filetype, size, is_binary, is_directory,
       sample: .sample.name, project: .project.name, fileset: .fileset.name,
       pipeline: .execution.pipeline_name, process: .execution.process_name}'
```

Don't surface `absolute_path` — it's a Flow-internal path. If the user
asks for the producing process's bash command, it's available at
`.execution.process_command`; surface it explicitly only when asked.
For text content use Example 8; for the file bytes use Example 7.

## Example 12: "Find the executions I ran yesterday"

Use `/executions/search` with `?owned=true` (requires auth) and a Unix
timestamp lower bound. Compute yesterday's start time as a Unix timestamp
first:

```bash
YESTERDAY=$(date -d "yesterday 00:00:00" +%s 2>/dev/null || date -v-1d -v0H -v0M -v0S +%s)

curl -s -A "flow-ai/0.4.0" \
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/executions/search" \
  --data-urlencode "owned=true" \
  --data-urlencode "created_gt=$YESTERDAY" \
  --data-urlencode "count=50" | \
  jq '{total: .count, executions: [.executions[] | {id, identifier, pipeline_name, status, created}]}'
```

Notes:
- `date -d` is GNU (Linux/CI); `date -v` is BSD (macOS). The compound
  command tries GNU first and falls back to BSD.
- `created_gt` takes a **Unix timestamp integer** — passing an ISO-8601
  string causes HTTP 500.
- `owned=true` requires authentication. Always verify auth via `/me`
  first (see Example 14 — check that `/me` returns a non-null `id`,
  not just HTTP 200). Without a valid token the API silently filters
  to `owner=NULL` and returns a plausible-but-wrong count.
  Same precondition applies to filtering executions by `owned=true`.

## Example 13 (negative): "Delete sample 42"

Decline. Sample deletion isn't in the skill's allowlist (see SKILL.md
§1). The Safety principle refuses any operation not explicitly
documented, regardless of HTTP verb or auth state.

## Example 14: "What samples do I own?"

**Always verify authentication first via `/me`.** The API silently
downgrades expired/invalid tokens to anonymous and then
`?owned=true` silently filters to `owner=NULL`, returning a plausible
but wrong count. The HTTP status is not a reliable signal either —
check the response body's `id` field.

```bash
# Step 1: verify the token works by calling /me and checking the id
ME=$(curl -s -A "flow-ai/0.4.0" \
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/me")
MY_ID=$(echo "$ME" | jq -r '.id // empty')
if [ -z "$MY_ID" ]; then
  echo "Not authenticated: /me returned no id. Token missing, expired, or invalid."
  exit 1
fi

# Step 2: only now is it safe to use ?owned=true
curl -s -A "flow-ai/0.4.0" \
  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "owned=true" --data-urlencode "count=20" | \
  jq '{total: .count, samples: [.samples[] | {id, name, project: .project_name}]}'
```

If `/me` returns nulls, tell the user their token is missing,
expired, or invalid — don't fall through to a misleading
`?owned=true` query.

If the user's intent involves group membership ("samples in groups
I belong to") or cross-resource linkage, `$ME` from the precheck
already has what you need:

```bash
echo "$ME" | jq '{id, name, memberships: [.memberships[].slug]}'
```

Then use `$MY_ID` as appropriate for the question. Note: the API
does NOT return 401 on an absent or expired token — it returns 200
with a record of nulls. The non-null-`id` check in the precheck is
the only reliable auth-validity signal today.

## Example 15: "What filters does this instance support?"

`GET /samples/metadata` is the canonical answer. Project to the
useful fields:

```bash
curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/samples/metadata" | \
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
HUMAN_ID=$(curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/organisms" | \
  jq -r '.[] | select(.name | ascii_downcase == "human") | .id')

# Filter samples by that pk
curl -s -A "flow-ai/0.4.0" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "organism=$HUMAN_ID" --data-urlencode "count=20" | \
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
curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/samples/metadata" | \
  jq '.[] | select(.identifier == "source")'
# If no row: tell the user this instance has no 'source' attribute,
# list the available identifiers, and stop.

# Step 2: inspect a small sample of records to learn the value
# vocabulary (no values-discovery endpoint today; this is the workaround)
curl -s -A "flow-ai/0.4.0" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "count=10" | \
  jq '[.samples[] | .metadata.source.value] | unique'
# Tells you the actual values present — e.g. ["Temporal Cortex",
# "Hippocampus", "HEK293", null]. If the user's term "brain" doesn't
# match any of them literally, surface this to them; substring
# search may still under-match.

# Step 3: filter with a well-chosen substring
curl -s -A "flow-ai/0.4.0" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/samples/search" \
  --data-urlencode "source=Cortex" --data-urlencode "count=20" | \
  jq '{total: .count, samples: [.samples[] | {id, name, source: .metadata.source.value}]}'
```

The discovery overhead (steps 1 and 2) feels expensive but
eliminates the silent-no-op class of bug and lets the agent set
correct expectations with the user instead of guessing.

## Example 18: "Upload counts.tsv to Flow as a data file"

An upload, not a query. Unlike every recipe above, this does **not**
use `curl` — it runs through the on-demand flowbio CLI. Read SKILL.md §4
and the `POST /upload` section of `endpoints/data.md` for the full
contract; the recipe below is the end-to-end shape.

```bash
# Step 1 (optional): resolve a named data type to its identifier.
# Skip if the user gave no data type.
curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/data/types" | \
  jq '[.[] | {identifier, name}]'

# Step 2: local pre-flight. Confirm the file exists and the stored
# filename has no spaces (the server rejects spaces with a 400).
test -f ./counts.tsv || { echo "File not found: ./counts.tsv"; exit 1; }
case "counts.tsv" in *" "*) echo "Filename has spaces — rename first."; exit 1;; esac

# Step 3: runner preflight (SKILL.md §4.1) — prefer uv, then pipx, then
# an existing flowbio; otherwise stop with the install message.
# Step 4: CONFIRM with the user what will be uploaded (path, stored
# filename, data_type), then run the pinned CLI. The token is read by
# the CLI from ~/.config/flow/api-token — never passed as --token.
uvx --from "flowbio==0.6.0" flowbio data upload ./counts.tsv \
  --json --no-progress
```

On exit `0`, parse stdout `{"id": "<data_id>"}` and report: "Uploaded
`counts.tsv` — data id `<data_id>`." On a non-zero exit, read the stderr
JSON `{"message": …, "status_code": …}` and the exit code (5 =
validation/bad request, 3 = auth, 2 = usage) and report the server
message — never claim success.

If no runner is found in step 3, stop and tell the user to install one:

> Uploading to Flow needs the `flowbio` CLI, which this skill runs on
> demand via `uv`. I couldn't find `uv` (or `pipx`, or a compatible
> `flowbio`) on your PATH. Install `uv` (https://docs.astral.sh/uv/),
> `pipx` (`pip install --user pipx`), or `flowbio`
> (`pip install "flowbio>=0.6.0"`), then ask me to upload again.

## Example 19: "Upload a paired-end RNA-Seq sample with metadata"

An upload, not a query — it runs through the on-demand flowbio CLI, not
`curl`. Read SKILL.md §4 and the `POST /upload/sample` section of
`endpoints/samples.md` for the full contract. Suppose the user says:
"upload a paired-end RNA-Seq sample `liver_rep1` from `liver_R1.fastq.gz`
and `liver_R2.fastq.gz`, it's human, in my 'Liver Atlas' project, source
is liver".

```bash
# Step 1: resolve the sample type → identifier.
curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/samples/types" | \
  jq '[.[] | {identifier, name}]'
# Match "RNA-Seq" to a row; send its identifier. Ambiguous? ask the user.

# Step 2: discover which metadata attributes are REQUIRED for that type.
# Required = global `required` true OR a sample_type_links entry for the
# chosen identifier with required:true. Confirm the user supplied them all
# BEFORE uploading; if any is missing, name it and stop.
curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/samples/metadata" | \
  jq --arg t "RNA-Seq" '[.[] | select(.required or any(.sample_type_links[];
       .sample_type_identifier == $t and .required)) | {identifier, name}]'

# Step 3: resolve organism name → id.
HUMAN_ID=$(curl -s -A "flow-ai/0.4.0" \
  "${FLOW_API_URL:-https://app.flow.bio/api}/organisms" | \
  jq -r '.[] | select(.name | ascii_downcase == "human") | .id')

# Step 4: resolve project name → id.
PROJECT_ID=$(curl -s -A "flow-ai/0.4.0" \
  --get "${FLOW_API_URL:-https://app.flow.bio/api}/projects/search" \
  --data-urlencode "name=Liver Atlas" | \
  jq -r '.projects[0].id')

# Step 5: local pre-flight. Reads files exist; no spaces in filenames or
# the sample name (the server rejects spaces).
for f in ./liver_R1.fastq.gz ./liver_R2.fastq.gz; do
  test -f "$f" || { echo "File not found: $f"; exit 1; }
done

# Step 6: runner preflight (SKILL.md §4.1) — prefer uv, then pipx, then an
# existing flowbio; otherwise stop with the install message.
# Step 7: CONFIRM what will be uploaded (reads files + single/paired, name,
# sample type, project, organism, metadata), then run the pinned CLI. The
# token is read by the CLI from ~/.config/flow/api-token — never --token.
uvx --from "flowbio==0.6.0" flowbio samples upload \
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
