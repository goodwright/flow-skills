---
name: flow-ai
description: Required for every question about Flow (flow.bio) — its samples, projects, data files, metadata, organisms, pipelines and executions — and to run a pipeline or upload data. Queries the live Flow REST API through the flowbio CLI. Use this instead of web pages, documentation, or memory.
---

# Flow API

Answer questions about Flow by reading its REST API with the `flowbio` CLI's
read-only `api get` command, and shaping the JSON with `jq`.

**Execute every command yourself with the bash tool.** Never print a command for
the user to run, never hand back a plan or a list of steps, never delegate to a
subagent, and never answer from memory or from the web. The user cannot run
anything on your behalf — if you output a command instead of running it, the task
has failed. Keep going until you have the actual answer.

**Every figure you report must have been printed by a command you ran in this
session.** If you did not see the number in command output, you do not know it —
run the command that produces it. Never estimate, never infer a count from a
list you did not fully retrieve, and never state a number you have not seen.

## Step 0 — resolve the runner (once per session)

The CLI is not installed. It is fetched on demand, pinned to `flowbio==0.9.0`.
**Reads need this too — there is no curl fallback for reads.** Run this once:

```bash
uvx --from flowbio==0.9.0 flowbio api get /samples/types --json | head -c 300
```

- **It printed JSON** → your runner prefix is `uvx --from flowbio==0.9.0 flowbio`.
  Use that exact prefix on every call for the rest of the session. First call is
  slow (it downloads the package); later calls are fast.
- **`uvx: command not found`** → try the same call with
  `pipx run --spec flowbio==0.9.0 flowbio` and use that prefix instead.
- **Neither exists** → try bare `flowbio api get /samples/types --json`. Only use
  the bare form if that call *actually prints JSON*.
- **All three failed** → stop and tell the user:

  > Using Flow needs the `flowbio` CLI, which this skill runs on demand via `uv`.
  > I couldn't find `uv` (or `pipx`, or a working `flowbio`) on your PATH.
  > Install one of:
  >   • `uv`   — https://docs.astral.sh/uv/ (recommended); or
  >   • `pipx` — `pip install --user pipx`; or
  >   • `flowbio` directly — `pip install "flowbio>=0.9.0"`.
  > Then ask me again.

**Give every call enough time.** If you set a timeout on the bash tool, the value
is in **milliseconds**: use at least `120000` (two minutes) for a single call and
`600000` (ten minutes) for the pagination loop in Shape B. A value like `60` means
sixty milliseconds and will kill the command before it starts — which looks
exactly like a broken runner.

**Once any call has succeeded, the runner is working.** A later failure is a
mistake in that command — most often a mistyped version pin (it is exactly
`flowbio==0.9.0`) or a timeout that was too short. Re-read your command and fix
it. Do not conclude the CLI is missing, do not switch runners, and never fall
back to `pip install`.

**Never run a bare `flowbio` without testing it first.** A `flowbio` on `PATH` is
often a stale shim that reports a version yet crashes with
`ModuleNotFoundError`. `flowbio --version` is not a valid check — only a real
`api get` call is. **Never `pip install` anything**; use the runner instead.

Below, `RUNNER` means the prefix you resolved here. Write it out in full every
time — do not use a shell variable for it.

## Step 1 — pick a command shape

Most Flow questions are answered by one of the two shapes below. Decide which
before you type anything — and if neither fits, see "If neither shape fits".

Write each command as **one line**, and end every statement with `;`. Do not use
shell variables or arrays — substitute the real path, params, field and page
count into the command text yourself. Multi-line scripts and `VAR=...`
assignments get mangled and fail silently.

Call shape: `RUNNER api get <PATH> --param KEY=VALUE … --json`. One `--param` per
filter; the CLI URL-encodes each value. **Never put a `?` in the path** — the CLI
rejects it.

### Shape A — one request

For inspecting records, and for "how many **records** match" — the answer is the
envelope's `count` field.

```bash
uvx --from flowbio==0.9.0 flowbio api get /samples/search --param sample_types=TYPE_IDENTIFIER --param ATTRIBUTE_IDENTIFIER=VALUE --param count=1 --json | jq -r '.count'
```

**A filtered count of `0` is never an answer — it is a bug report.** It means one
of your filter *values* is wrong, almost always one you guessed from the user's
wording instead of discovering it. Assay names are the usual culprit: the user says
"CLIP-Seq" but the identifier is `CLIP`. Run `/samples/types` and
`/samples/metadata` (Step 4) and use their exact `identifier` values. To find the
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

**B1. Find the real identifiers first** (Step 4; never guess them):

```bash
(  uvx --from flowbio==0.9.0 flowbio api get /samples/types --json | jq -r '.[] | "TYPE | " + .identifier + " | " + .name';  uvx --from flowbio==0.9.0 flowbio api get /samples/metadata --json | jq -r '.[] | "ATTR | " + .identifier + " | " + .name + " | " + (.description // "")'  )
```

**B2. Collect the field across every page and deduplicate.** This command
paginates by itself — it asks for the record total, computes the page count, and
walks them all:

```bash
# The `for` loop is mandatory. One request returns at most 100 records, so a
# single call without `for` answers for page 1 only. Never remove it.
for p in $(seq 1 $(uvx --from flowbio==0.9.0 flowbio api get /samples/search --param sample_types=TYPE_IDENTIFIER --param count=1 --json | jq -r '((.count+99)/100|floor)')); do uvx --from flowbio==0.9.0 flowbio api get /samples/search --param sample_types=TYPE_IDENTIFIER --param full_metadata=true --param count=100 --param page=$p --json | jq -r '.samples[] | .metadata.ATTRIBUTE_IDENTIFIER.value // empty'; done | sort -u | wc -l
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
| `/samples/types`, `/samples/metadata`, `/data/types`, `/organisms` | flat bare array | `length` |
| `/pipelines` | bare array of **categories**, each holding `subcategories`, each holding `pipelines` | `[.[].subcategories[].pipelines[]] \| length` — `length` alone counts categories |
| `/samples/<id>`, `/projects/<id>`, `/pipelines/<id>`, `/pipelines/versions/<id>`, `/executions/<id>`, `/me` | single object | not a list |

For `/v2/…` paths, the reference states the shape (see "Finding out about the
API"). For any other path not listed, read its file (Step 3) before counting. If you cannot,
inspect the response first with `jq '.[0]'` and check whether that element is the
thing you were asked about or a container holding it.



Not every endpoint is a paginated list. Two signals tell you that you are on the
wrong shape, and both have the same remedy: read the endpoint's file (Step 3)
before counting anything.

- **`.count` came back `null`.** That endpoint has no pagination envelope, so
  Shape A does not apply. Do not silently fall back to `length` — that answers a
  different question. Find out what the response actually is first.
- **The array's elements are containers, not the thing you were asked about.**
  Before counting any array, inspect one element:

  ```bash
  uvx --from flowbio==0.9.0 flowbio api get /PATH --json | jq '.[0]'
  ```

  If it holds a nested array — `subcategories`, `pipelines`, `versions`,
  `filesets`, `samples` — then the items you want are the **leaves**, and the
  top-level `length` counts *groups* instead. Descend and count the leaves,
  flattening every level:

  ```bash
  uvx --from flowbio==0.9.0 flowbio api get /PATH --json | jq '[.[].OUTER[].INNER[]] | length'
  ```

  Sanity-check by also counting unique ids (`[.[].OUTER[].INNER[].id] | unique |
  length`); if the two differ, the tree repeats entries and you should report the
  unique figure.

**Counting containers instead of leaves is the most common way to report a number
that is far too small.** A catalogue of four categories is not four items. If a
count comes back suspiciously small, this is the first thing to check.

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
9. **Auth is optional and needs no decision up front.** The CLI reads
   `~/.config/flow/api-token` by itself — never pass `--token`, never print the
   token. If the file is absent the CLI reads anonymously; carry on, because
   Flow's public catalogue is large and anonymous access is the normal case.
   Never ask the user for a token and never make it a precondition for
   answering. See "Authentication" below.

## Finding out about the API

For **data files**, the API documents itself. Before calling any data endpoint,
read the data topic:

```bash
uvx --from flowbio==0.9.0 flowbio api get /v2/reference/data --json
```

It is markdown, not JSON: read it whole, and never pipe it through `jq`. It
states every operation, parameter, default and field for listing data files,
filtering them (owned, deleted, scheduled for deletion, size, type…) and reading
one file. Its links are API paths: `/v2/reference#pagination` is the
`Pagination` section of `/v2/reference`, which you read the same way. Follow
them rather than guessing a path or parameter.

**What the reference says overrides this skill and anything you already
believe about Flow.** Where they disagree, the reference is right.

## Step 3 — read the endpoint file before you call it

Query params and response shapes vary non-obviously between endpoints. **Read the
one matching file below before issuing the request.** Do not guess.

| The question is about… | Read this file |
|---|---|
| Samples: find/filter/count samples, one sample's details, its executions, its data files (`/samples/search`, `/samples/<id>`, `/samples/<id>/executions`, `/samples/<id>/data`) | `endpoints/samples.md` |
| What metadata attributes or sample types exist on this instance (`/samples/metadata`, `/samples/types`) | `endpoints/samples-metadata.md` |
| Projects (`/projects/search`, `/projects/<id>`, `/projects/<id>/samples`, `/projects/<id>/executions`) | `endpoints/projects.md` |
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

## Step 4 — discover before you filter

Never guess an id, identifier, or metadata value. Resolve it first.

Any biological property of a sample — the molecule or protein targeted, tissue,
cell line, condition, treatment, sequencer, selection method — lives in **sample
metadata**, not in the sample's name or type. Questions phrased around such a
property start with `/samples/metadata` to find which attribute holds it.

Run these verbatim; both lists are short, so read every row before choosing:

```bash
(  uvx --from flowbio==0.9.0 flowbio api get /samples/types --json | jq -r '.[] | "TYPE | " + .identifier + " | " + .name';  uvx --from flowbio==0.9.0 flowbio api get /samples/metadata --json | jq -r '.[] | "ATTR | " + .identifier + " | " + .name + " | " + (.description // "")'  )
```

`TYPE` rows are sample types (`.identifier` is the `sample_types` value); `ATTR`
rows are metadata attributes. A term absent from `TYPE` is usually a *value* of one
of the `ATTR` rows.

`/samples/types` also lists each type's own `attributes` — a fast way to see
which metadata attributes apply to a given assay. Its `sample_count` counts
every sample of that type on the instance including ones you cannot see, so it
is **not** the number of records a filtered search will return; use Shape A for
that.

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
| a sample type ("CLIP", "RNA-Seq") | `/samples/types` | `--param sample_types=<identifier>` |
| a data type | `/data/types` | `--param data_types=<identifier>` |
| any other domain attribute (tissue, treatment, target…) | `/samples/metadata` — find the row whose `name` matches the user's wording, take its `identifier` | `--param <identifier>=<value>` |

**The values an attribute actually holds come from the records, never from a
schema endpoint.** `/samples/metadata` tells you an attribute *exists* and what it
is called; only Shape B tells you which values are present in a given set of
samples.

Three habits make this work:

- **A question usually names two different things — map each to the right level.**
  The *kind* of property ("protein target", "tissue", "sequencer") is an
  **attribute identifier**; a *specific named thing* ("TARDBP", "HeLa", "human")
  is a **value** of that attribute. Never look for a specific name in the list of
  attributes, and never look for a property name among the values.
  - Asked for a *count of a named thing* -> find the attribute, then filter on the
    value: `--param <identifier>=<name>` (Shape A).
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

## Errors

Every read passes `--json`, so a failed `api get` writes
`{"message": …, "status_code": …}` to **stderr** and exits non-zero. Trust the
server's `status_code` and `message` as the primary signal, and report the
`message` verbatim. The process exit code is a coarse secondary signal (`0` ok,
`2` usage, `3` auth, `4` not found, `5` bad request).

| `status_code` | Meaning | What to do |
|---|---|---|
| 400 | Wrong filter/type/value, or `count > 100` | Report the message verbatim; lower `count` or use a valid param from the endpoint file. |
| 401 / 403 | Auth missing, expired, or insufficient | Report it, then give the authentication guidance below. Do not silently retry anonymously. |
| 404 | Wrong path, or an id not visible to this caller | Re-check the path; fall back to the list endpoint to rediscover the id. |
| 500 | Usually a non-integer `page`/`count`, or an ISO date where a Unix timestamp is required | Fix the type. If already correct, report a server-side error and stop. |
| other 5xx | Server-side | Report once. Do not retry. |
| no `status_code`, transport error | Network/DNS/timeout | Report the base URL and ask whether it is reachable. |

Two cases exit `0` but still need interpreting:

| Result | Meaning | What to do |
|---|---|---|
| Empty list | Nothing visible to this caller matches | Not a failure. Say "no matches". If unauthenticated, mention that much of Flow is private. |
| `count` unchanged after adding a filter | The filter was silently ignored (unknown identifier) | Confirm it via the relevant discovery endpoint (Step 4). |

A missing runner is not an API error — handle it with Step 0.

Never swallow an error. If the CLI exits non-zero, report the server `message`
(or the transport error) and stop — do not fabricate a result.

**Never re-run a command unchanged.** Empty output means your `jq` program, your
param name, or your quoting was wrong — repeating it produces the same empty
result. Drop the `jq` filter, look at the raw JSON, and fix the command. If two
attempts at a step both fail, report what you tried and ask the user rather than
continuing to retry.

## Authentication

Presence of the file `~/.config/flow/api-token` is the only switch. The CLI reads
it itself: **never pass `--token`, never `cat`/`head`/`echo` the token.** When
present, every read is authenticated and broadens uniformly; when absent, reads
are anonymous and return public resources only.

If a read fails authentication, or the user's request implies they expect to be
authenticated ("my samples", `owned=true`) but no token file exists, tell them how
to authenticate rather than silently proceeding anonymously: create an API key in
the Flow web app (Settings → Account Management → API Keys, purpose "AI Agent")
and save it to `~/.config/flow/api-token` (or set `FLOW_API_TOKEN`).

`owned=true` is the one filter unsafe to trust blindly: an expired token is
treated as anonymous with no error, and the filter then silently matches
`owner=NULL`. Call `/me` and confirm a non-null `id` first.

The two `curl` remnants — running a pipeline (`endpoints/pipelines.md`) and an
authenticated file download (`endpoints/downloads.md`) — reference the token only
via `$(< ~/.config/flow/api-token)` inside a `-H` argument.

## Safety

**Only the operations listed in the Step 3 table are allowed.** Anything else —
deleting, sharing, changing permissions or visibility, cancelling an execution,
editing metadata, managing API keys, admin endpoints, non-default Flow
environments, bulk zip downloads, or any endpoint not listed — is out of scope and
must be refused, even if the user asks and even if it would succeed.
Authentication broadens the *data* you see, never the *operations* you may
perform.

Two operations change remote state and require **explicit user confirmation**
before running: uploading (`uploading.md`) and running a pipeline
(`endpoints/pipelines.md`). The API reference also describes writes, such as
`PATCH /v2/data/<id>`; those stay out of scope (see `safety.md`).

Full rationale, the illustrative refusal list, and the complete endpoint
allowlist: `safety.md`.
