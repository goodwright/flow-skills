# Samples — metadata schema, options & types

Discovery endpoints for *what you can filter on* and *what values are legal*:

- `GET /samples/metadata` — metadata attribute schema for this instance
- `GET /samples/metadata/<identifier>/options` — controlled value set for one attribute
- `GET /samples/types` — sample-type enum (also lists each type's `attributes`)
- `GET /samples/types/<identifier>` — single sample-type detail

To then *use* an identifier or value as a filter, see `endpoints/samples.md`.

## `GET /samples/metadata`

Discovery endpoint for the metadata attributes defined on this Flow
instance. **This is the canonical "what filters can I use on
`/samples/search`?" endpoint.** Metadata attributes are user-defined
per-instance — admins of each Flow deployment curate their own set.
Hard-coded identifiers in skill docs would be wrong on most
instances, so always discover at runtime.

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array of `MetadataAttribute` rows,
  ordered by the admin-configured `order` field.
- **Per-item fields:**
  - `identifier` (str — the filter key on `/samples/search`; e.g.
    `"source"`, `"condition"`, `"experimental_method"` on instances where
    those exist)
  - `name` (str — human-readable label)
  - `description` (str — admin-supplied description)
  - `in_table` (bool — true if this attribute appears in the
    `/samples/search` list-view's `metadata` projection by default)
  - `has_options` (bool — true if the attribute has a controlled
    value set; false for free-text)
  - `all_sample_types` (bool — true if this attribute applies to all
    sample types; false if it is restricted to specific types listed
    in `sample_type_links`)
  - `regex_validator` (str|null — regex applied to values if set)
  - `required` (bool), `required_for_public` (bool), `is_list` (bool),
    `allow_user_terms` (bool), `allow_annotation` (bool),
    `url_pattern` (str|null), `order` (int)
  - `sample_count` (int — number of distinct samples that carry a
    value for this attribute)
  - `sample_type_links` (array — per-sample-type requirement overrides;
    empty when `all_sample_types=true` and no per-type rules exist.
    Each item: `{sample_type_identifier: str, sample_type_name: str,
    required: bool, required_for_public: bool}`)

**Key behaviour to surface to agents:**

- This is the source of truth for legal `?<identifier>=value`
  filters on `/samples/search`. Call this first when the user asks
  a metadata-scoped question — never guess at identifiers.
- Identifiers vary by instance. The skill never asserts that a
  specific identifier exists; it teaches discovery.
- `has_options=true` attributes have a controlled value set — filter
  values should come from that set. Call
  `GET /samples/metadata/<identifier>/options` (below) to list the legal
  values, then filter `/samples/search?<identifier>=<value>`.
- `has_options=false` attributes are free-text — they have no options,
  so the options endpoint returns an empty set for them. Substring matching
  on `/samples/search?<identifier>=<substring>` is the only filter
  mechanism. Values may follow instance-specific conventions
  (e.g. a `source` attribute holding `"Temporal Cortex"`,
  `"Hippocampus"`, etc.) — substring search alone may under-match
  if the user's natural-language term doesn't appear literally.

## `GET /samples/metadata/<identifier>/options`

Lists the controlled value set (the "options") for a single metadata
attribute. **This is the value-discovery counterpart to
`GET /samples/metadata`:** that endpoint tells you which attribute
*identifiers* exist; this one tells you the legal *values* for an
attribute whose `has_options` is `true`. Use it to turn a vague
natural-language value into an exact option before filtering
`/samples/search?<identifier>=<value>`.

- **Auth:** none required. Authentication broadens the result set: an
  authenticated caller additionally sees their **own** not-yet-validated
  options (terms they submitted that an admin hasn't validated). Anonymous
  callers — and authenticated callers, for everyone else's options — see the
  **validated** (admin-curated) set only. Pass `?validated=true` (below) when
  you want strictly the curated set regardless of who is calling.
- **Path param:** `<identifier>` — a metadata attribute `identifier` from
  `GET /samples/metadata`. Unknown identifier → **HTTP 404**
  `{"error": "Not found"}`. (An attribute with `has_options=false` exists but
  has no options, so it returns `200` with an empty `options` array and
  `count: 0` — not a 404.)
- **Query params:**

| Name        | Type | Default | Behaviour |
|-------------|------|---------|-----------|
| `validated` | str  | (none)  | When present, restricts by validation state. `validated=true` → only validated (admin-curated) options; **any other value** (e.g. `validated=false`) → only un-validated options within the caller's visible set (i.e. the caller's own pending terms). The check is literal `== "true"`. |
| `value`     | str  | (none)  | Case-insensitive substring (`__icontains`) on the option `value`. Use to narrow a large option set. |

- **No `page` param, and a hard cap of 100.** The `options` array contains at
  most the **first 100** options (ordered by `value` ascending). There is no
  pagination — if `count` exceeds 100, the extra options are **silently
  omitted**. Detect this by comparing `count` to the returned array length; when
  truncated, narrow with `?value=<substring>` rather than assuming you've seen
  every option.
- **Response envelope:** `{"count": int, "total_count": int, "options": [...]}`.
  - `total_count` — total options visible to the caller **before** the
    `validated`/`value` filters are applied.
  - `count` — total options matching **after** the `validated`/`value` filters.
    This is the cross-set total, **not** the page size, so it may exceed the
    100-item `options` length (see the cap above).
  - `options` — array (≤100) of `{id, value, validated}`.
- **Per-item fields:**
  - `id` (str — the option's pk; not usually needed for read-only filtering)
  - `value` (str — the legal value; pass this verbatim to
    `/samples/search?<identifier>=<value>`)
  - `validated` (bool — `true` for admin-curated options, `false` for
    un-validated user-submitted terms)
- **How to use it (discovery → filter):**
  1. `GET /samples/metadata` → find the attribute and confirm `has_options=true`.
  2. `GET /samples/metadata/<identifier>/options` → read the legal `value`s
     (optionally `?value=<substring>` to find the match for the user's term).
  3. `GET /samples/search?<identifier>=<value>` with an exact option value.
     Search matches metadata by substring, so an exact option value filters
     precisely without the under-match risk that free-text attributes carry.

This endpoint only exposes the read-only listing. Creating, merging,
editing, or deleting options are admin operations and are out of scope for
this skill (see `safety.md`).

## `GET /samples/types`

Discovery endpoint for the sample-type enum on this instance. Used
to resolve a user-named sample type (e.g. "RNA-seq") to its
identifier for the `?sample_types=<identifiers>` filter on
`/samples/search`.

Small, finite list per instance (6 types on app.flow.bio today).

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array, ordered by name.
- **Per-item fields:**
  - `identifier` (str — the filter key, e.g. `"RNA-Seq"`,
    `"ChIP-Seq"`; pass to `?sample_types=` on `/samples/search`)
  - `name` (str — human label; often the same as `identifier`)
  - `description` (str — admin-supplied description)
  - `sample_count` (int — number of samples of this type)
  - `attributes` (array — the subset of metadata attributes that
    (1) have controlled options defined AND (2) have at least one
    value recorded against a sample of this type. This is a dynamic
    intersection, not a static schema declaration — an attribute that
    applies to all sample types will appear here for every type that
    has samples using it. For the full attribute schema, call
    `GET /samples/metadata`.)

## `GET /samples/types/<identifier>`

Single sample-type detail.

- **Auth:** none required.
- **Path param:** `<identifier>` from the list view (NOT a numeric pk —
  identifiers are the canonical lookup key). Returns HTTP 404 if not found.
- **Response shape:** a single object with the same fields as the
  list-item: `identifier`, `name`, `description`, `sample_count`,
  `attributes`. No additional fields are added at the detail level.

## Discovery pattern for sample types

1. `GET /samples/types` → list available types.
2. Match the user's term against `name` (case-insensitive).
3. Pass the matched `identifier` to
   `/samples/search?sample_types=<identifier>` (comma-separated for
   multiple).
