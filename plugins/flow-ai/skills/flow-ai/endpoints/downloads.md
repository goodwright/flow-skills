# Downloads endpoint

## `GET /downloads/<data_id>/<filename>`

Direct single-file download for a public Data row.

- **Auth:** public when the Data is anonymous-readable. No auth header is
  required for public data. (The endpoint also accepts `?token=...`, a
  `flow_refresh_token` cookie, or a `Bearer` header for authenticated
  callers — none of those apply here.)

**With authentication:** any Data the caller has access to is
downloadable through this endpoint. Unlike reads (which go through
`flow-cli api get`), a download is a raw-byte transfer done with `curl`, so
attach the token to the curl yourself for private data —
`-H "Authorization: Bearer $(< ~/.config/flow/api-token)"` — preserving the
token discipline in "Authentication" in `SKILL.md` (never print it). Omit the header
for public data.

- **Path parameters:**
  - `<data_id>` is a **Data primary key**, NOT a `BulkDownloadJob` id, despite
    the `/downloads/` URL prefix. The bulk-download flow uses a different
    pattern and a UUID, and is out of scope for this skill.
  - `<filename>` must equal `data.filename` exactly. Mismatched filename →
    404 (with one exception below).
- **Query params:**

| Name     | Type | Default | Behaviour |
|----------|------|---------|-----------|
| `direct` | str  | (unset) | Truthy value (e.g. `?direct=yes`) serves inline. Unset serves as attachment with `Content-Disposition: attachment; filename=<name>`. |

- **Response body.** The file bytes.
- **Always pass `--fail-with-body`.** Without it curl writes an error
  response into the `-o` file and exits `0`, so a refused download looks like a
  successful one. With it, a refusal exits `22` and the `-o` file holds the
  server's text instead of the file's bytes: read that text, report it, and
  delete the file.
- **Refusals.** None of them is JSON (other endpoints return
  `{"error": ...}`):
  - **410 Gone**, plain-text body `Data <id> (<filename>) was deleted on
    <YYYY-MM-DD>` — the file's content was deleted under the data retention
    policy. Its record stays visible, so the id and filename are right, but
    the bytes are gone for good. Tell the user the file was deleted and when;
    don't retry, and don't look for another way to fetch it.
  - **404, empty body** — id not found / removed / not ready, filename
    mismatch, or data not readable by this caller.
- **HTML asset edge case.** If `data.filetype == "html"` and the URL
  filename doesn't match `data.filename`, the view tries the filename as
  a relative href inside the HTML so reports can load their own
  CSS/images. For agent downloads, treat the rule as "filename must
  match exactly". A link to a file whose content was deleted answers 410 as
  above.
- **Bulk multi-file downloads (out of scope).** The
  `POST /downloads/...` → tar.gz flow is auth-gated and not covered here.
