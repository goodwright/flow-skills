# Flow concepts

What Flow's records are and how they relate, as its REST API shows them. The
endpoint files hold each endpoint's parameters, fields and visibility rules;
this file says what the things they return are.

## Resource hierarchy

```
project ──< sample ──< fileset ──< data
pipeline ──< pipeline_version ──< execution ──< process_execution ──< data
```

A project groups samples (e.g. one experiment, one paper). A sample is a
biological sample with metadata; it owns one or more filesets, which are
collections of related files (e.g. paired-end FASTQs). Data are individual
files: a sample's raw inputs sit in its filesets, and a pipeline's outputs
belong to the step (process execution) of the run that produced them.

A pipeline is a Nextflow workflow definition with one or more versions. A
pipeline version is the unit you actually run; an execution is a single
run of a pipeline version, and its process executions are the run's steps.

## Identifiers

Records have numeric ids, returned as **strings** in JSON. An id is stable
for the lifetime of its record. Some things are named by a string instead:
an organism's `id` is a short code (`Hs`), sample types and metadata
attributes have an `identifier`, a user has a `username`, and an execution
has an `identifier` and a `uuid`.

A filter that picks out one particular thing takes its id or identifier,
never its display name. Text filters such as `name`, `owner` and `project`
are the exception: they match a substring. So to filter by something the user named ("the
rna-seq pipeline", "human samples"), discover its id first:

1. List the catalog endpoint with a coarse filter (or no filter).
2. Identify the right item by name in the response.
3. Use that item's id or identifier as the filter value in the next call.

## Audience model

Flow resources have three audiences:

- **Public** — visible without authentication. Visibility rules are
  per-resource (see each endpoint file); they are not a single
  `is_public` flag.
- **Owned** — owned by the calling user. Requires auth.
- **Shared** — shared with the calling user via Flow's permission system.
  Requires auth.

This skill targets a single audience-agnostic surface. Every endpoint it
uses returns the **union** of resources visible to the caller: public
resources always, plus owned and shared resources when a token is
attached. There is no "mode" — whether a token is present (see
"Authentication" in `SKILL.md`) determines which audience the response
covers.

"Public" is a strict subset, not a default. Most data on Flow is
private. An empty result from an unauthenticated request means
"nothing matches this query under the public visibility rule", not
"the API is broken". Authenticating typically returns more rows.

## Discovery endpoints

Flow exposes runtime discovery for the entities and attributes that
vary per instance: `GET /v2/metadata-attributes` (legal metadata attribute
identifiers), `GET /organisms` (organism enum), `GET /v2/sample-types`
(sample-type enum), `GET /me` (authenticated identity),
`GET /users/search` (user directory).

When the user's question involves these concepts, the agent's first
move is the discovery endpoint, not the search endpoint:

- "human samples" → `/organisms` (resolve "human" to its `id`) → `/samples/search?organism=<id>`
- "rna-seq samples" → `/v2/sample-types` (resolve to identifier) → `/samples/search?sample_types=<identifier>`
- "samples where tissue is X" → `/v2/metadata-attributes` (does `tissue` exist on this instance? what is its actual identifier?) → `/samples/search?<identifier>=<value>`
- "samples I own" → `/me` (confirm a non-null `id`) → `/samples/search?owned=true`

Why: metadata attributes are user-defined per Flow instance. There is
no global Flow vocabulary; the same product runs at different
organisations with different attribute schemas. The skill cannot
hard-code identifiers; agents must discover at runtime.

## Where the details live

- **Pipelines** are grouped into categories and subcategories; you run one
  of a pipeline's versions. `endpoints/pipelines.md`.
- **Samples**: their search, detail, executions and files, and who can see
  them. A sample's inline `filesets` are only its raw inputs, while
  `/samples/<id>/data` adds every pipeline output traced back to it.
  `endpoints/samples.md`.
- **Projects**: their search, detail, samples and executions.
  `endpoints/projects.md`.
- **Executions**: a run's states, its steps and polling it.
  `endpoints/executions.md`.
- **Data files**: listing and reading them is `GET /v2/reference/data`;
  previews and data types are `endpoints/data.md`; a single file's bytes
  are `endpoints/downloads.md`, by data id (not a bulk-download job id).
