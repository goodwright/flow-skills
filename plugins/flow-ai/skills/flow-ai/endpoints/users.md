# Users endpoints

Two related endpoints for the user/identity surface: `/me` (the
authenticated caller's record) and `/users/search` (search the user
directory).

## `GET /me`

The authenticated caller's user record. Use this to resolve "what is
my user id?" — needed when a recipe references the caller's pk (e.g.
`/samples/search?owner=<my_id>`).

For ownership questions ("samples I own", "projects I own"), still use
`/me` first as an auth gate: `/samples/search?owned=true` silently treats
a missing or invalid token as anonymous and returns a misleading count (it
does not 401), so confirm `/me` succeeds before trusting an `owned=true`
result. `/me` is likewise needed when:

- The intent involves group membership ("samples in groups I'm in") —
  `/me` returns the caller's `memberships`.
- You need the caller's pk to cross-reference across resources.
- You want to check whether the caller is an admin (`is_admin`).

- **Auth:** required. With a missing, expired, or invalid token, `/me`
  returns **401** (`flowbio api get` exit `3`) — unlike the search
  endpoints, which accept a bad token as anonymous and return 200. So a
  failed `/me` is the reliable "not authenticated" signal:
  - success with a non-null `id` → genuinely authenticated.
  - 401 / exit 3 → no valid token; treat as anonymous and tell the user
    their token is missing, expired, or invalid (and how to authenticate,
    `SKILL.md` section 3).
- **Query params:** none.
- **Response shape:** a single object with:
  - `id` (str — the caller's user pk, **stringified** integer; present on
    a successful call. An unauthenticated caller gets a 401 instead of a
    record — see the Auth note above)
  - `username` (str|null)
  - `name` (str — display name)
  - `image` (str | null — avatar URL)
  - `is_admin` (bool)
  - `can_run_pipelines` (bool)
  - `can_impersonate` (bool)
  - `has_ssh_key` (bool)
  - `impersonator` (object | null — set when the caller is being impersonated)
  - `features` (object — feature flags, e.g. `{"impersonation": bool}`)
  - `memberships` (array — group memberships the caller belongs to as a
    member or admin; each entry: `{name, slug, is_admin}`)
  - `notifications` (object — `{count, unread_count, notifications: [...]}`)

## `GET /users/search`

Search the user directory by name or username. Useful for:

- Confirming a user exists or disambiguating between users with similar
  names.
- Getting a user's canonical `username`, which can then be passed as a
  precise substring to `/samples/search?owner=<username>` (the `owner`
  filter matches across name, username, and email — using the exact
  username reduces false matches).
- Inspecting a user's group memberships via the `groups` field in each
  result row.

Note: this endpoint does **not** expose a user `id`. The `owner` filter
on `/samples/search` (and similar endpoints) is a substring match, not
a pk lookup — pass the `username` (or name substring) directly.

- **Auth:** none required — the endpoint is public.
- **Query params:**

| Name           | Type | Default | Behaviour |
|----------------|------|---------|-----------|
| `page`         | int  | `1`     | Paginator page. |
| `count`        | int  | `10`    | Page size. Max 100. |
| `name`         | str  | (none)  | Substring on `name` or `username`. **Note:** the param is `name`, not `query`. |
| `exclude_group`| str  | (none)  | Group slug; exclude users already in this group. |

- **Response shape:** `{"count": int, "page": int, "users": [...]}`.
- **Per-item fields** (from the live API — no `id` or `email` is exposed):
  - `username` (str)
  - `name` (str — display name)
  - `image` (str — avatar URL or empty string)
  - `groups` (array — group memberships; each entry: `{slug, name, created, image}`)

## Discovery pattern

For "what samples does `<name>` own?":

1. `GET /users/search?name=<name>` → pick the right user by `name`
   or `username` (check how many rows came back; refine the search if
   there are too many matches).
2. Use the `username` to cross-reference. Note that `/users/search`
   does not expose `id` — to filter samples by owner pk, use
   `/samples/search?owner=<username_or_name_substring>` directly
   (samples `owner` filter matches across name, username, and email).

For "what samples do I own?":

- `GET /samples/search?owned=true` — simplest path, no `/me` needed.
- Only call `/me` if you need the caller's pk or group memberships for
  a cross-resource operation.
