# Design: rework flow-ai reads onto `flowbio api get`

**Date:** 2026-07-15
**Status:** approved (pending written-spec review)

## Problem

The `flow-ai` skill performs every Flow read with `curl`, embedding the token
via a `$(< ~/.config/flow/api-token)` command substitution in a `-H` flag.
Claude Code will not prefix-allowlist a command containing `$(...)`, so every
read re-prompts for approval. A bespoke opt-in hook
(`hooks/flow-read-approve.sh`, gated on `FLOW_AI_AUTO_APPROVE_READS=1`) exists
solely to suppress those prompts.

The `flowbio` CLI now ships a read-only GET passthrough,
`flowbio api get <PATH> [--param KEY=VALUE …]`, which resolves the token
itself (from `~/.config/flow/api-token`, or anonymous when absent) and honours
`FLOW_API_URL`. Moving reads onto it lets the CLI own authentication, produces
a stable secret-free command prefix that is allowlistable by normal means, and
removes the reason the hook exists.

## Goals

- Replace curl-based Flow **reads** with `flowbio api get`.
- Let the CLI own authentication so reads no longer embed a token substitution.
- Remove the read-approve hook; rely on standard Claude Code allowlisting.
- Surface actionable authentication guidance on auth failure / when the user
  expects to be authenticated.

## Non-goals

- Adding a POST/mutation passthrough to the flowbio CLI.
- Changing the upload flows (already CLI-based) beyond the shared version pin.
- Preserving a distinct `flow-ai` User-Agent on reads (accepted loss — see
  Consequences).
- Targeting non-default Flow environments; bulk multi-file (zip) downloads.

## Design

### 1. Read mechanism

Every in-scope GET currently issued as
`curl -s -A "flow-ai/…" --get "…/<PATH>" --data-urlencode "k=v"` becomes:

```
flowbio api get <PATH> --param k=v --json | jq …
```

- `<PATH>` is relative to the base URL (leading slash optional), e.g.
  `/samples/search`.
- Query params become repeated `--param KEY=VALUE` (the CLI URL-encodes each
  value); never interpolate user input into the path. A `?` in the path is a
  CLI usage error — always use `--param`.
- The CLI writes the raw response body verbatim to stdout, so all existing
  `jq` projection and output-discipline rules carry over unchanged.
- `--json` is always passed. For `api get` it does **not** reshape the success
  body (still raw, for `jq`); it only makes error output machine-readable.
- Base URL and token are resolved by the CLI from `FLOW_API_URL` and
  `~/.config/flow/api-token` — the skill no longer interpolates either.

### 2. Curl remnants (deliberately unchanged)

Two paths cannot move to `api get` and stay on curl:

- **`POST /pipelines/versions/<id>/run`** — `api get` is GET-only. Remains a
  curl JSON POST, still gated behind explicit confirmation (its approval prompt
  is by design). Token discipline (`$(< …)` in the header, never printed) is
  preserved for this call.
- **`GET /downloads/<data_id>/<filename>`** — a raw-byte download. `api get`
  returns the body as *text* (`get_text`/`emit_raw(body: str)`) and there is no
  `data download` command, so binary downloads stay on `curl -o`, unchanged.

Everything else moves to `api get`, including the discovery reads inside the
run flow (`/pipelines`, `/pipelines/<id>`, `/pipelines/versions/<id>`,
`/samples/search`, `/me`, etc.). Text-based `/data/<id>/contents` previews
return JSON and DO move to `api get`.

### 3. Runner & version

- Single version pin bumped **`flowbio==0.7.0` → `flowbio==0.9.0`**. `0.9.0` is
  the first release with `api get` and also carries every upload command, so
  one pin covers reads and uploads.
- The existing on-demand runner preflight (prefer `uvx`, then `pipx run`, then
  a compatible `flowbio` already on PATH, else stop) now runs before the
  **first CLI call of any kind** — read or upload — not only before uploads.
- **Hard requirement, no curl fallback for reads.** If no runner is found, stop
  with the install message (reworded from "Uploading to Flow needs…" to "Using
  Flow needs the `flowbio` CLI…"); do not silently fall back to curl.
- Per-machine prefix consistency falls out of the fixed preflight priority: a
  given machine always resolves to the same runner, so its read command prefix
  is stable and allowlistable.

### 4. Approvals — hook removal

- Delete `hooks/flow-read-approve.sh`, `hooks/flow-read-approve.test.sh`, and
  `hooks/hooks.json`; remove any hook wiring from `plugin.json`.
- Document recommended allowlist entries (README/skill) — one per runner
  prefix, so the operator can opt in once or approve ad hoc:
  - `Bash(flowbio api get:*)`
  - `Bash(uvx --from flowbio==0.9.0 flowbio api get:*)`
  - `Bash(pipx run --spec flowbio==0.9.0 flowbio api get:*)`
- No executable machinery ships to replace the hook.

### 5. Authentication guidance

- Reads work anonymously by default (public resources only).
- When a call returns an **auth error**, or the user's request implies they
  expect to be authenticated (e.g. "my samples", `owned=true`), the skill
  surfaces how to authenticate: place a Flow API token in
  `~/.config/flow/api-token` (or set `FLOW_API_TOKEN`); the token comes from
  their Flow account. It does not fabricate a settings URL.
- The auth-validity self-check (call `/me`, require a non-null `id` before
  trusting `owned=true`) is preserved, executed via `api get`. The Flow API
  returns 200-with-nulls for an absent/expired token rather than 401, so this
  check remains the only reliable signal.

### 6. Error handling

Read error handling flips from HTTP-status semantics (curl) to the CLI's
output contract:

- Always request `--json`, so failures print a machine-readable envelope on
  **stderr**: `{"message": …, "status_code": …}`.
- Treat the server's **`status_code` + readable `message`** as the primary,
  trustworthy signal — it is more precise than the coarse process exit code.
- Exit codes are a secondary/coarse signal: `0` ok, `2` usage, `3` auth,
  `4` not found, `5` bad request.
- On auth failure, chain into the authentication guidance (§5).
- The curl remnants (run POST, byte download) keep their existing HTTP-status
  handling.

### 7. Files touched

- `skills/flow-ai/SKILL.md` — frontmatter description (reads via CLI, not
  curl); §1 token discipline scoped to the curl remnants; §2 scope note; §3
  configuration (drop curl skeletons; describe `api get`, `--json`, auth
  resolution); §4 preflight reword (applies to reads too); §6 querying
  patterns (`--param`, drop the "always `-A flow-ai`" read rule); §8 error
  handling (exit-code + `--json` envelope).
- `skills/flow-ai/examples.md` — rewrite read recipes to `api get`; keep run
  (Examples 22/23) and download (Example 7) on curl; update the auth preamble.
- `skills/flow-ai/endpoints/*.md` — swap curl GET examples to `api get`;
  `pipelines.md` keeps the POST section; `downloads.md` keeps `curl -o`.
- `hooks/` — delete the three hook files; update `plugin.json` (remove hook
  refs) and README (remove hook docs, add the allowlist recommendation).
- Version/User-Agent strings — bump/retire the `flow-ai/0.8.0` read UA
  references as they are removed from read calls.
- `plugin.json` — bump the plugin/skill's own `version` (currently `0.9.0`) to
  the next release, and update its description if the read-mechanism wording
  changes.

## Consequences

- Reads identify to the Flow API as the **flowbio CLI's** User-Agent, not
  `flow-ai/x`. The "identify AI-agent traffic" intent shifts from a `flow-ai`
  UA to "traffic arrives as the flowbio CLI." Accepted. Restoring a distinct
  marker would be a flowbio CLI feature request, out of scope here.
- Reads now depend on a runner (uv/pipx/flowbio) being present. On a machine
  with none, reads stop with an install message instead of working via curl.
  This is the intended single-path trade-off.
- First read on a fresh machine pays the `uvx`/`pipx` environment-resolution
  cost; subsequent calls reuse the cached environment.

## Verification

- Read recipes issue `flowbio api get … --json` and parse stdout via `jq`.
- Auth error path prints the `{"message", "status_code"}` envelope and the
  skill responds with authentication guidance.
- Missing-runner path stops with the reworded install message; no curl
  fallback occurs for reads.
- Run POST and byte download still use curl and remain confirmation/size
  gated.
- Hook files are gone and nothing references them; the CI description-length
  guard still passes.
