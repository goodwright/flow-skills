# flow-ai local evals

Runs the plugin's scenarios against a local Flow stack and reports pass rate,
Flow calls and tokens per scenario and model.

## Set up the stack (in a flow-api checkout)

```bash
cd api
docker compose -f docker_compose.yaml up -d --build
mkdir -p ~/.config/flow
(umask 077 && docker compose -f docker_compose.yaml exec -T api uv run python - \
    < evals/seed_data_evals.py > ~/.config/flow/eval-api-token)
```

## Run

```bash
cd evals
export EVAL_EXPECTED_FILE=<flow-api>/api/evals/data_expected.json
uv run run.py --scenario '004*' --scenario '019*' --scenario '02[01]*'
uv run compare.py runs/<before> runs/<after>
```

A scenario filter is required: each run spends subscription time, so there is
no run-everything default. `--model` (repeatable) overrides the default pair.
`EVAL_TOKEN_FILE` defaults to `~/.config/flow/eval-api-token`; `FLOW_API_URL`
to `http://localhost:8019`. Transcripts and `summary.json` land in
`runs/<timestamp>/`.

Each agent runs in an empty temporary directory with only `plugins/flow-ai`
loaded, your own settings, plugins and MCP servers left out, and the README's
read allowlist, so a write stalls instead of running. The token reaches the
agent through its environment only.

`compare.py` exits non-zero when, for any model, the after run has a lower pass
rate or spends more tokens than the before run.

## Test

```bash
cd evals && uv run pytest
```
