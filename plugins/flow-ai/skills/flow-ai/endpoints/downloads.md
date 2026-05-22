# Downloads endpoint

## `GET /downloads/<data_id>/<filename>`

Direct single-file download for a public Data row.

- **Auth:** public when the Data is anonymous-readable. No auth header is
  required for public data. (The endpoint also accepts `?token=...`, a
  `flow_refresh_token` cookie, or a `Bearer` header for authenticated
  callers — none of those apply here.)

**With authentication:** any Data the caller has access to is
downloadable through this endpoint. The same `Authorization: Bearer …`
header (see `SKILL.md` section 3) applies; the endpoint already
accepts it.

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

- **Response body.** The file bytes. In prod the response is empty with
  `X-Accel-Redirect` and nginx serves the file — transparent to
  `curl -o <file>` either way.
- **Refusals.** All failures return bare HTTP **404 with no JSON body**
  (other endpoints return `{"error": ...}`): id not found / removed /
  not ready, filename mismatch, or data not anonymous-readable.
- **HTML asset edge case.** If `data.filetype == "html"` and the URL
  filename doesn't match `data.filename`, the view tries the filename as
  a relative href inside the HTML so reports can load their own
  CSS/images. For agent downloads, treat the rule as "filename must
  match exactly".
- **Bulk multi-file downloads (out of scope).** The
  `POST /downloads/...` → tar.gz flow is auth-gated and not covered here.
