# Organisms endpoints

The organism enum on this Flow instance. Used to resolve a user-named
organism ("human", "mouse") to its primary key for `?organism=<pk>` on
`/samples/search`.

Small, finite list, curated per instance. Call `/organisms` to
discover what's available — never assume a particular set.

## `GET /organisms`

- **Auth:** none required.
- **Query params:** none.
- **Response shape:** a bare JSON array (no pagination envelope).
- **Per-item fields:**
  - `id` (str — **not** an integer; a short alphabetic code, e.g. `"Hs"` for Human)
  - `name` (str — common name, e.g. `"Human"`)
  - `latin_name` (str — scientific name, e.g. `"Homo sapiens"`)
  - `latest_fileset` (object | null — the most recently created genome reference
    fileset for this organism that has at least one ready, non-private Data file;
    null if none exists. Shape: `{id, name, long_name, url, created, can_edit, sample, organism: {id, name}, data: [{id, filename, size, category}]}`)

## `GET /organisms/<id>`

- **Auth:** none required.
- **Path param:** `<id>` is the string code from the list view (e.g. `"Hs"`).
- **Response shape:** a single object with `id`, `name`, `latin_name`, and
  `filesets` (array — all genome reference filesets for this organism that have
  at least one ready, non-private Data file; each entry: `{id, name, created, organism_name, data: [{id, filename, filetype, size}]}`).

## Discovery pattern

When a user names an organism, the canonical sequence is:

1. `GET /organisms` to retrieve the full list.
2. Match the user's term against `name` or `latin_name` (case-insensitive).
3. Pass the matched `id` to `/samples/search?organism=<id>`.

The `id` is a short string code, not an integer. Pass it as-is. Do **not**
pass the user's term directly as `?organism=<name>` — the API expects the
code and will silently no-op on a name string.
