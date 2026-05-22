# Pipelines endpoint

## `GET /pipelines`

- **Auth:** public, no auth required.
- **Query params:** **none**. The view ignores `request.GET` entirely — no
  `page`, no `count`, no `filter`. Passing query params is silently a no-op.
- **Pagination:** **none**. The full catalog is returned in a single response
  as a **bare JSON array** (not the `{count, page, ...}` envelope used by the
  sample/project list endpoints).
- **Response shape.** Top-level array of category objects. Tree:
  - Category: `{name, description, subcategories: [...]}`
  - Subcategory: `{name, description, pipelines: [...]}`
  - Pipeline: `{id, name, description, execution_count, is_nfcore, prepares_genome}`
    - `id` — string (stringified integer pk).
    - `description` — taken from the most recent active version.
    - `execution_count` — total runs ever for this pipeline.
- **Per-pipeline version list is NOT exposed** on this endpoint. Agents
  cannot answer "what version of pipeline X" from `/pipelines`. That
  requires authenticated endpoints, which are out of scope here.
- **Implicit visibility filter (not user-controllable).** For unauthenticated
  callers, only pipelines with at least one active, non-private version
  appear. Empty subcategories and categories are dropped.

**With authentication:** the catalogue broadens to include pipelines
the caller can see via project access, ownership, or sharing. The URL
is unchanged. When the token file (see `SKILL.md` section 3) is
present, the agent must attach the `Authorization: Bearer …` header
on this call too — broadening is automatic from there.
