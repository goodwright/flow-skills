---
name: flow-ai
description: Required for every question about Flow (flow.bio) — its samples, projects, data files, metadata, organisms, pipelines and executions — and to run a pipeline or upload data. Queries the live Flow REST API through the flowbio CLI. Use this instead of web pages, documentation, or memory.
---

# Flow API

Answer questions about Flow by reading its REST API with the `flowbio` CLI's
`api get` command, and shaping the JSON with `jq`. Make the changes a user asks
for — create a project, edit a sample or its metadata — with `api post` and
`api patch`, as "Changing records" below describes.

**Execute every command yourself with the bash tool.** Never print a command for
the user to run, never hand back a plan or a list of steps, never delegate to a
subagent, and never answer from memory or from the web. The user cannot run
anything on your behalf — if you output a command instead of running it, the task
has failed. Keep going until you have the actual answer.

**Every figure you report must have been printed by a command you ran in this
session.** If you did not see the number in command output, you do not know it —
run the command that produces it. Never estimate, never infer a count from a
list you did not fully retrieve, and never state a number you have not seen.

## Step 0 — check the CLI (once per session)

Every call goes through `flow-cli`, which runs the `flowbio` CLI at the version
this skill is written against, fetching it on demand. **Reads need it too —
there is no curl fallback for reads.** Run this once:

```bash
flow-cli api get /v2/sample-types --json | head -c 300
```

- **It printed JSON** → the CLI works; use `flow-cli` for every call. The first
  call is slow (it downloads the package); later calls are fast.
- **`flow-cli: command not found`** → the skill was installed without its
  plugin. Run `scripts/flow-cli` from this skill's directory instead, by its full
  path, and use that path wherever this skill writes `flow-cli`.
- **It printed "Using Flow needs the `flowbio` CLI…"** → stop and give the user
  that message.
- **It crashed with `ModuleNotFoundError` or `ImportError`** → the `flowbio`
  already installed on this machine is broken. Stop and tell the user
  to install `uv` (https://docs.astral.sh/uv/), which `flow-cli` prefers, then
  ask again.
- **It failed in any other way**, such as a network error (which also prints a
  traceback), a Flow error or a timeout → report the error output as it is.

**Give every call enough time.** If you set a timeout on the bash tool, the value
is in **milliseconds**: use at least `120000` (two minutes) for a single call and
`600000` (ten minutes) for the pagination loop in Shape B. A value like `60` means
sixty milliseconds and will kill the command before it starts — which looks
exactly like a broken CLI.

**Once any call has succeeded, the CLI is working.** A later failure is a
mistake in that command, most often a timeout that was too short. Re-read your
command and fix it; do not conclude the CLI is missing.

**Never call `flowbio`, `uvx` or `pipx` yourself, and never `pip install`
anything.** `flow-cli` picks how to run the CLI and which version.

## Step 1 — pick a command shape

Most Flow questions are answered by one of the two shapes below. Decide which
before you type anything — and if neither fits, see "If neither shape fits".

Write each command as **one line**, and end every statement with `;`. Do not use
shell variables or arrays — substitute the real path, params, field and page
count into the command text yourself. Multi-line scripts and `VAR=...`
assignments get mangled and fail silently.

Call shape: `flow-cli api get <PATH> --param KEY=VALUE … --json`. One `--param` per
filter; the CLI URL-encodes each value. Put the pair in double quotes when the
value has a space, or a character such as `&`, `;`, `*` or `(`:
`--param "name=Liver Atlas"`. Unquoted, the shell splits it and the CLI fails
with `unrecognized arguments`. **Never put a `?` in the path** — the CLI
rejects it.

### Shape A — one request

For inspecting records, and for "how many **records** match" — the answer is the
envelope's `count` field.

```bash
flow-cli api get /samples/search --param sample_types=TYPE_IDENTIFIER --param "ATTRIBUTE_IDENTIFIER=VALUE" --param count=1 --json | jq -r '.count'
```

**A filtered count of `0` is never an answer — it is a bug report.** It means one
of your filter *values* is wrong, almost always one you guessed from the user's
wording instead of discovering it. Assay names are the usual culprit: the user says
"CLIP-Seq" but the identifier is `CLIP`. Run `/v2/sample-types` and
`/v2/metadata-attributes` (Step 4) and use their exact `identifier` values. To find the
offending filter, drop them one at a time and see which one restores a non-zero
count.

Any metadata attribute identifier from Step 4 works as a `--param` filter — that
is how you count the records holding a particular value. Drop the params you don't
need. **Filter server-side like this rather than fetching records and searching
their values yourself**: a value absent from page 1 is not a value absent from the
data.

**If `.count` prints `null`, stop.** This endpoint is not a paginated list, so
Shape A does not apply and the answer is *not* `length`. Go to "Response shapes"
below before counting anything.

### Shape B — paginated aggregate

For "how many **distinct / unique / different** X", "which X are there", "list all
X" — anything needing a *field* from every record.

**A single request can never answer these.** Page size is capped at 100, so one
request sees at most 100 of possibly thousands of records. Envelope `count` is not
the answer either — it counts records, not distinct values.

**B1. Find the real identifiers first** with the discovery command in Step 4;
never guess them.

**B2. Collect the field across every page and deduplicate.** This command
paginates by itself — it asks for the record total, computes the page count, and
walks them all:

```bash
# The `for` loop is mandatory. One request returns at most 100 records, so a
# single call without `for` answers for page 1 only. Never remove it.
for p in $(seq 1 $(flow-cli api get /samples/search --param sample_types=TYPE_IDENTIFIER --param count=1 --json | jq -r '((.count+99)/100|floor)')); do flow-cli api get /samples/search --param sample_types=TYPE_IDENTIFIER --param full_metadata=true --param count=100 --param page=$p --json | jq -r '.samples[] | .metadata.ATTRIBUTE_IDENTIFIER.value // empty'; done | sort -u | wc -l
```

Drop the `| wc -l` to list the values instead of counting them.

**`sort -u | wc -l` goes after `done`, never inside the loop.** Inside, it
deduplicates each page separately and the counts are then summed, inflating the
answer — a value repeated on ten pages would be counted ten times. Deduplication
must see all pages at once, so it belongs on the loop's combined output.

`TYPE_IDENTIFIER` and `ATTRIBUTE_IDENTIFIER` are **placeholders and are not valid
values.** Replace both with the real identifiers from B1 — and keep both copies of
`TYPE_IDENTIFIER` in sync. They are deliberately invalid so that forgetting to
substitute one returns `0` rather than a plausible wrong number.

**A result of `0` is never the answer.** It means a placeholder is unsubstituted,
an identifier is misspelled, or `full_metadata=true` is missing. Go back to B1.

This makes one CLI call per page and takes a minute or two on a large result set.
That is expected — let it finish rather than reaching for a shortcut.

Two ways people get this wrong, both of which silently answer for page 1 only:

- **Never** replace this with a single request carrying `page=1`, or with no
  `page` at all, and treat the result as complete. That is exactly the trap the
  loop exists to avoid.
- **Never** copy values out of a response into a follow-up command — no
  `echo "…" | sort -u`, no pasting a list back into the shell. Deduplicate inside
  the single pipeline above, so every page is included.

Other notes:

- `full_metadata=true` is what makes metadata visible in a list response. Without
  it `.metadata` is nearly always empty and you will count zero.
- To collect a top-level field instead of a metadata attribute, replace the `jq`
  program with e.g. `'.samples[] | .organism.name // empty'`.
- Keep `// empty` so records missing the field are skipped, not counted as `null`.
- Every value the attribute holds counts. Do not filter or `grep` the collected
  values — see Step 4.
- Same shape for `/projects/search` and `/executions/search` — swap the path
  and the `.samples[]` root. Data files are listed by `/v2/data`, which pages
  differently; its reference says how.

Report the number, say what you counted, and name anything you excluded.

**State how many pages you walked and the record total.** This is your own
correctness check: if the total is above 100 and you walked one page, the answer
is wrong — you read at most 100 of the records. Redo it with the loop before
answering.

### If neither shape fits

#### Response shapes

Flow returns three different shapes. Counting the wrong one is the most common
error on this API, so identify the shape before writing any `length` or `.count`.

| Path | Shape | Number of items is |
|---|---|---|
| `/samples/search`, `/projects/search`, `/executions/search`, `/users/search` | envelope `{count, page, <resource>: [...]}` | `.count` (total across all pages) |
| `/v2/sample-types`, `/v2/metadata-attributes`, `/data/types`, `/organisms` | flat bare array | `length` |
| `/pipelines` | bare array of **categories**, each holding `subcategories`, each holding `pipelines` | `[.[].subcategories[].pipelines[]] \| length` — `length` alone counts categories |
| `/samples/<id>`, `/projects/<id>`, `/pipelines/<id>`, `/pipelines/versions/<id>`, `/executions/<id>`, `/me` | single object | not a list |

For `/v2/…` paths, the reference states the shape (see "Finding out about the
API"). For any other path not listed, read its file (Step 3) before counting. If
you cannot, inspect one element first — it may be a container holding the thing
you were asked about, not the thing itself:

```bash
flow-cli api get /PATH --json | jq '.[0]'
```

If it holds a nested array — `subcategories`, `pipelines`, `versions`,
`filesets`, `samples` — then the items you want are the **leaves**, and the
top-level `length` counts *groups* instead. Descend and count the leaves,
flattening every level:

```bash
flow-cli api get /PATH --json | jq '[.[].OUTER[].INNER[]] | length'
```

Sanity-check by also counting unique ids (`[.[].OUTER[].INNER[].id] | unique |
length`); if the two differ, the tree repeats entries and you should report the
unique figure.

A catalogue of four categories is not four items: if a count comes back
suspiciously small, check for containers first.

## Step 2 — rules for every call

1. Always pass `--json`. On success it leaves the body untouched for `jq`; on
   failure it makes the error machine-readable.
2. One `--param KEY=VALUE` per filter. Repeat the flag for multi-valued params.
   Never interpolate user input into the path.
3. Always set the page size explicitly. On the endpoints in this skill's files it
   is `count`: the default is **10**, so omitting it silently gives you ten
   records, and `count>100` returns HTTP 400. `/v2/…` endpoints name and cap it
   differently; their reference says how.
4. Use the **exact** parameter name from the endpoint file — `sample_types`, not
   `sample_type`. A misspelled parameter is silently ignored, not rejected.
5. **Wrap every `jq` program in single quotes**: `jq -r '.[] | .name'`. Double
   quotes break the moment the program contains a string literal, and the shell
   error surfaces as empty output rather than as a failure.
6. **Keep `jq` programs trivial.** Never use string interpolation (`"\(.x)"`) or
   `printf`-style formatting — the escaping is fragile and fails silently. To
   inspect a list of records, project the two or three fields you need by joining
   them with `+`, e.g.
   `jq -r '.[] | .identifier + " | " + .name + " | " + (.description // "")'`.
   Keep `description` on discovery calls — it is what tells apart similar-sounding
   attributes (a "Source" holding cell lines and tissues vs a "Condition" holding
   experimental conditions). Dumping every
   field of every row (`jq -c '.[]'`) can be tens of kilobytes and crowds out
   everything else you need to remember. To extract one field, use
   `jq -r '.[].fieldname'`.
7. **Never `jq 'select(...)'` on a name you guessed.** Dump the whole list
   (projecting `identifier` and `name`) and read it. A `select` that matches nothing is
   indistinguishable from "this instance has none of those" — see Step 4.
8. `FLOW_API_URL` overrides the base URL; forward it only if the user set it.
   Never pass `--base-url` otherwise.
9. **Auth is optional and needs no decision up front**, and the CLI handles the
   token itself. See "Authentication" below.

## Finding out about the API

The `/v2/…` endpoints document themselves. `/v2/reference` lists the topics,
and each topic page states every operation, parameter, default, field and
error, and who each operation admits:

| Topic | Covers |
|---|---|
| `/v2/reference/data` | listing data files, filtering them (owned, deleted, scheduled for deletion, size, type…), reading one file |
| `/v2/reference/samples` | the sample types and metadata attributes a sample can carry and the values they take, the rules for which attribute applies and is required, and editing a sample and its metadata |
| `/v2/reference/projects` | creating a project and changing its name or description |

Before calling an endpoint of a topic, read its page:

```bash
flow-cli api get /v2/reference/samples --json
```

It is markdown, not JSON: read it whole, and never pipe it through `jq`. Its
links are API paths: `/v2/reference#pagination` is the `Pagination` section of
`/v2/reference`, which you read the same way. Follow them rather than guessing
a path, parameter or field.

**What the reference says overrides this skill and anything you already
believe about Flow.** Where they disagree, the reference is right.

## Step 3 — read the endpoint file before you call it

Query params and response shapes vary non-obviously between endpoints. **Read the
one matching file below before issuing the request.** Do not guess.

| The question is about… | Read this file |
|---|---|
| Samples: find/filter/count samples, one sample's details, its executions, its data files (`/samples/search`, `/samples/<id>`, `/samples/<id>/executions`, `/samples/<id>/data`) | `endpoints/samples.md` |
| What sample types and metadata attributes exist, which apply to a type, and which values an attribute takes (`/v2/sample-types`, `/v2/metadata-attributes`, `/v2/metadata-attributes/<identifier>/options`) | `GET /v2/reference/samples` — see "Finding out about the API" |
| Editing a sample: its name, type, organism, PubMed id or metadata (`PATCH /v2/samples/<id>`) | `GET /v2/reference/samples`, then "Changing records" |
| Projects (`/projects/search`, `/projects/<id>`, `/projects/<id>/samples`, `/projects/<id>/executions`) | `endpoints/projects.md` |
| Creating a project, or changing its name or description (`POST /v2/projects`, `PATCH /v2/projects/<id>`) | `GET /v2/reference/projects`, then "Changing records" |
| Data files: list, search or count them, which are deleted or scheduled for deletion, one file's details (`/v2/data`, `/v2/data/<id>`) | `GET /v2/reference/data` — see "Finding out about the API" |
| Data files: contents preview, data types, uploading (`/data/<id>/contents`, `/data/types`) | `endpoints/data.md` |
| Pipelines, their versions, a version's run schema, **or running a pipeline** | `endpoints/pipelines.md` |
| Executions: search, or one execution's detail / polling a run (`/executions/search`, `/executions/<id>`) | `endpoints/executions.md` |
| Organisms (`/organisms`) | `endpoints/organisms.md` |
| Who am I / find a user (`/me`, `/users/search`) | `endpoints/users.md` |
| Downloading a file's bytes (`/downloads/<data_id>/<filename>`) | `endpoints/downloads.md` |
| Uploading anything, or running a pipeline (machinery, confirmation gate) | `uploading.md`, `endpoints/samples-upload.md` |
| Multi-step recipes for read questions | `examples.md` |
| Multi-step recipes for uploads and pipeline runs | `examples-write.md` |
| What a project / sample / fileset / execution *is* | `flow-concepts.md` |
| A call failed: what its status means and what to do | `errors.md` |

## Step 4 — discover before you filter

Never guess an id, identifier, or metadata value. Resolve it first.

Any biological property of a sample — the molecule or protein targeted, tissue,
cell line, condition, treatment, sequencer, selection method — lives in **sample
metadata**, not in the sample's name or type. Questions phrased around such a
property start with `/v2/metadata-attributes` to find which attribute holds it.

Run these verbatim; both lists are short, so read every row before choosing:

```bash
(  flow-cli api get /v2/sample-types --json | jq -r '.[] | "TYPE | " + .identifier + " | " + .name';  flow-cli api get /v2/metadata-attributes --json | jq -r '.[] | "ATTR | " + .identifier + " | " + .name + " | " + .description'  )
```

`TYPE` rows are sample types (`.identifier` is the `sample_types` value); `ATTR`
rows are metadata attributes. A term absent from `TYPE` is usually a *value* of one
of the `ATTR` rows.

`/v2/metadata-attributes` says which types each attribute applies to: every
type when `all_sample_types` is true, otherwise the types in its
`sample_types`. For one type, ask for just its attributes with
`--param sample_type=<identifier>`; an identifier no sample type has is
refused with a `422`, so resolve it from `/v2/sample-types` first. `/v2/reference/samples` states the rest of the rules (what is
required, what a public sample needs, options and free text). Neither list
counts samples; for how many records match, use Shape A.

**Attributes have two names, and you almost always want `identifier`.** `name` is
the human label ("Purification Target"); `identifier` is the machine key
(`purification_target`). The metadata bag on a sample is keyed by `identifier`,
and `identifier` is what filters accept — so `.metadata.purification_target.value`
works and `.metadata."Purification Target".value` silently yields nothing. Match
the user's wording against the `name` column, then use that row's `identifier`.

| User says | Call this first | Then filter with |
|---|---|---|
| a pipeline by name | `/pipelines` | the matched `id` |
| an organism ("human") | `/organisms` | `--param organism=<id>` |
| a sample type ("CLIP", "RNA-Seq") | `/v2/sample-types` | `--param sample_types=<identifier>` |
| a data type | `/data/types` | `--param data_types=<identifier>` |
| any other domain attribute (tissue, treatment, target…) | `/v2/metadata-attributes` — find the row whose `name` matches the user's wording, take its `identifier` | `--param "<identifier>=<value>"` |
| the legal values of an attribute with `has_options` | `/v2/metadata-attributes/<identifier>/options` (paged; `--param value=<substring>` narrows) | `--param "<identifier>=<value>"` |

**The values an attribute actually holds come from the records, never from a
schema endpoint.** `/v2/metadata-attributes` tells you an attribute *exists* and
what it is called, and its options are the values it *may* take; only Shape B
tells you which values are present in a given set of samples.

Three habits make this work:

- **A question usually names two different things — map each to the right level.**
  The *kind* of property ("protein target", "tissue", "sequencer") is an
  **attribute identifier**; a *specific named thing* ("TARDBP", "HeLa", "human")
  is a **value** of that attribute. Never look for a specific name in the list of
  attributes, and never look for a property name among the values.
  - Asked for a *count of a named thing* -> find the attribute, then filter on the
    value: `--param "<identifier>=<name>"` (Shape A).
  - Asked *which values exist* or *how many distinct* -> find the attribute, then
    aggregate its values (Shape B). Here the user's word names only the attribute:
    the values are the domain's own identifiers (gene symbols, cell lines,
    accessions) and will not contain the user's word, so never `grep` them for it
    and never drop values you don't recognise.
- **Print the whole discovery list and read every row** — project `identifier` and
  `name` as above rather than dumping all fields. These lists are short (under 30
  rows). Never
  `jq 'select(.name == "…")'` on the word the user used: the instance's wording
  rarely matches it, an assay the user calls "X-Seq" may have identifier `X`, and
  a `select` that matches nothing looks identical to "this instance has none".
- **Verify the filter was applied.** `/samples/search` silently ignores params it
  does not recognise, returning the *unfiltered* set with no error. After adding
  a filter, check that envelope `count` actually dropped. If it didn't, the
  parameter name or the value was wrong — fix it before going on.

Metadata identifiers and sample types differ per Flow instance — always discover
them at runtime, never assume.

## Step 5 — output discipline

- Pipe every response through `jq`, projecting only the fields asked for.
- Never paste more than ~20 lines of raw JSON into the answer. Summarise lists.
- Report the number you computed and how you computed it. Never estimate, and
  never fabricate a result if a call failed.

## Changing records

The writes this skill may make are listed under "Safety" below. Each is a
`/v2/…` operation, described in full by its reference topic: read the topic
page first, and send exactly the body it describes.

**Confirm before every write.** State the record, the fields and the values you
will send — and, when creating a project, whether it will be **public** or
private — and wait for the user's explicit yes. Never write on an inference.

Send the body as one line of JSON on stdin, inside single quotes. Write an
apostrophe inside a value as `\u0027` (`"Martin\u0027s samples"`): JSON reads it
as `'`, and a literal one would end the shell's quoting.

```bash
printf '%s' '{"name": "Liver Atlas", "description": "Bulk RNA-Seq of liver"}' | flow-cli api post /v2/projects --body - --json
```

```bash
printf '%s' '{"metadata": {"cell_line": {"value": "HeLa"}}}' | flow-cli api patch /v2/samples/SAMPLE_ID --body - --json
```

- An edit changes only what the body sends, so send only the fields the user
  asked to change. In a sample's `metadata`, an attribute left out keeps its
  value and `null` clears it.
- Use identifiers exactly as discovery returned them (Step 4): a sample type
  from `/v2/sample-types`, an attribute and its option values from
  `/v2/metadata-attributes`. Never guess one.
- Ids are strings of digits. Send them back exactly as a response gave them.
- On success the response is the record as it now stands; report what changed
  from it, not from what you sent.
- A write needs a token. Without one the CLI sends nothing: it exits `2` with
  "No credentials provided…". Give the authentication guidance below; never
  retry anonymously.

## Errors

Every call passes `--json`, so a failed call writes
`{"message": …, "status_code": …}` to **stderr** and exits non-zero. **When a
call fails, read `errors.md`** for what each status means and what to do. In
every case:

- Report the server's `message` verbatim, and trust its `status_code` over the
  exit code.
- On a `/v2/…` path, branch on `problem.code`, never on the message.
- Never swallow an error. Report it and stop; never fabricate a result.

Two cases exit `0` but still need interpreting:

| Result | Meaning | What to do |
|---|---|---|
| Empty list | Nothing visible to this caller matches | Not a failure. Say "no matches". If unauthenticated, mention that much of Flow is private. |
| `count` unchanged after adding a filter | The filter was silently ignored (unknown identifier) | Confirm it via the relevant discovery endpoint (Step 4). |

A missing CLI is not an API error — handle it with Step 0.

**Never re-run a command unchanged.** Empty output means your `jq` program, your
param name, or your quoting was wrong — repeating it produces the same empty
result. Drop the `jq` filter, look at the raw JSON, and fix the command. If two
attempts at a step both fail, report what you tried and ask the user rather than
continuing to retry.

## Authentication

Presence of the file `~/.config/flow/api-token` is the only switch. The CLI reads
it itself: **never pass `--token`, never `cat`/`head`/`echo` the token.** When
present, every read is authenticated and broadens uniformly; when absent, reads
are anonymous and return public resources only. Carry on anonymously: Flow's
public catalogue is large and anonymous access is the normal case. Never ask
the user for a token, and never make one a precondition for answering.

If a read fails authentication, or the user's request implies they expect to be
authenticated ("my samples", `owned=true`) but no token file exists, tell them how
to authenticate rather than silently proceeding anonymously: create an API key in
the Flow web app (Settings → Account Management → API Keys, purpose "AI Agent")
and save it to `~/.config/flow/api-token` (or set `FLOW_API_TOKEN`). Link them
to the full steps, which also cover Windows and file permissions:
https://github.com/goodwright/flow-skills/blob/main/README.md#getting-a-flow-api-key-optional

`owned=true` is the one filter unsafe to trust blindly: an expired token is
treated as anonymous with no error, and the filter then silently matches
`owner=NULL`. Call `/me` and confirm a non-null `id` first.

The one `curl` call, an authenticated file download (`endpoints/downloads.md`),
references the token only via `$(< ~/.config/flow/api-token)` inside a `-H`
argument.

## Safety

**Only the operations listed in the Step 3 table are allowed**, and the
refusals below win over any reference page that documents an operation. Anything else —
deleting, sharing, changing permissions or ownership, making anything private
public, moving a sample to another project, cancelling an execution, managing
API keys, admin endpoints, non-default Flow environments, bulk zip downloads,
or any endpoint not listed — is out of scope and must be refused, even if the
user asks and even if it would succeed. Authentication broadens the *data* you
see, never the *operations* you may perform.

These change remote state and require **explicit user confirmation** before
running:

- uploading (`uploading.md`) and running a pipeline (`endpoints/pipelines.md`);
- creating a project, `POST /v2/projects` (private unless the user asks for
  public, and the confirmation says which);
- changing a project's name or description, `PATCH /v2/projects/<id>`;
- changing a sample's name, type, organism, PubMed id or metadata,
  `PATCH /v2/samples/<id>`.

The reference describes other writes, such as `PATCH /v2/data/<id>`; reading
about an operation there does not make it allowed (see `safety.md`).

Full rationale, the illustrative refusal list, and the complete endpoint
allowlist: `safety.md`.
