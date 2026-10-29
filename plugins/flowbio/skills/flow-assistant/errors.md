# Errors

A failed `flow-cli` call writes `{"message": …, "status_code": …}` to stderr
(with `--json`) and exits non-zero. Trust the server's `status_code` and
`message` as the primary signal, and report the `message` verbatim. The exit
code is a coarse secondary signal (`0` ok, `2` usage, `3` auth, `4` not found,
`5` bad request or invalid input).

When the server names the parts of the request at fault, they are listed under
`errors`, and each entry's own message says more than the top-level one. On the
endpoints in this skill's files an entry is `{field, code, message}`. A `/v2/…`
path also returns the server's own error, an RFC 9457 Problem Details object,
under `problem`, and its entries are `{parameter | pointer, code, detail}`:

```json
{"message": "Invalid request", "status_code": 422,
 "errors": [{"parameter": "page", "code": "int_parsing", "detail": "Input should be a valid integer, …"}],
 "problem": {"type": "https://app.flow.bio/api/v2/reference#validation_error", "title": "Invalid request",
             "status": 422, "detail": "Invalid request", "code": "validation_error", "errors": […]}}
```

- **Branch on `problem.code`**, never on the message. The Errors section of
  `/v2/reference` says what each code means; `type` links to
  that code's section, so `…/v2/reference#not_found` is the `not_found` section
  of `api get /v2/reference`. Treat a code not documented there as the generic
  error for its `status_code`.
- **Each `errors` entry names what to fix**: `parameter` is a query or path
  parameter, `pointer` a JSON Pointer into the request body (`/imports/0/name`).
  Report its `detail` with the name.
- **On a 5xx, quote `problem.instance`** (`urn:uuid:…`) when it is present: it is
  the id that leads Flow's developers to the fault.

| `status_code` | Meaning | What to do |
|---|---|---|
| 400 | Wrong filter/type/value, a non-integer `page`/`count`, `count > 100`, or an ISO date where a Unix timestamp is required | Fix each field `errors` names, using a valid value from the endpoint file. |
| 500 on `/projects/search` or `/data/<id>/contents` | An ISO date in `created_gt`/`created_lt`, or a non-integer `position`: these two are not validated, so they fail as a server error | Fix the value as the endpoint file states it. |
| 422 | A `/v2/…` parameter or body is invalid (`validation_error`) | Fix each entry `errors` names, using the parameter or body as the reference states it. |
| 422 with an entry coded `refused_field` | The write sent a field the API never changes for this skill: visibility, ownership, or a sample's project | Do not retry it, and do not look for another way to make the change. Tell the user the entry's `detail` verbatim: it says why, and that they can make the change in the Flow web app. |
| 401 / 403 | Auth missing, expired, or insufficient | Report it, then give the authentication guidance ("Authentication" in `SKILL.md`). Do not silently retry anonymously. |
| 404 | Wrong path, or an id that does not exist or is not visible to this caller; Flow reports the two alike | Re-check the path; fall back to the list endpoint to rediscover the id. Tell the user it does not exist or they may not see it, not which. |
| 410 | The file's content was deleted under the retention policy; the message says which file and when | Report it as deleted, with the date. Do not retry, and do not try another endpoint to reach the same file. |
| 5xx | Server-side fault | Report once, quoting `problem.instance` if present. Do not retry. |
| no `status_code`, transport error | Network/DNS/timeout | Report the base URL and ask whether it is reachable. |
