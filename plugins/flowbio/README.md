# Flow

Lets an AI agent query [Flow](https://flow.bio), a bioinformatics platform
built by [Goodwright](https://goodwright.com), and upload data to it on your
behalf.

## What it does

Its `flow-assistant` skill mostly reads, but it can also make a few
confirmed changes on Flow: create projects, edit samples and their
metadata, run pipelines, and upload generic data files, demultiplexed
samples, and multiplexed reads with an annotation sheet. With it, an agent can answer questions and run
uploads like:

- "What pipelines are available on Flow?"
- "How many samples do I own?"
- "What was the last successful execution of the RNA-Seq pipeline on
  sample X, and what data files did it produce?"
- "Download the FASTQ for data file 67890."
- "Upload counts.tsv to Flow as a data file."
- "Upload a paired-end RNA-Seq sample with this metadata."
- "Upload these multiplexed reads with my annotation sheet."

See [`skills/flow-assistant/SKILL.md`](skills/flow-assistant/SKILL.md)
for the current capabilities.

## Install

In Claude Code:

```text
/plugin install flowbio --marketplace goodwright/flow-skills
```

## What it runs and sends

Every call to Flow, except a file download, goes through `flow-cli`, a small
launcher in
[`skills/flow-assistant/scripts/flow-cli`](skills/flow-assistant/scripts/flow-cli).
It runs Goodwright's [`flowbio`](https://pypi.org/project/flowbio/) CLI from
PyPI, pinned to one exact version: through `uvx` if you have `uv`, else
`pipx`, else a `flowbio` you have installed at that version. If none of those
is available, it prints how to install `uv` and stops. An agent with a
package tool of its own, such as Claude Science's, may then install that
exact `flowbio` version with it.

The CLI talks only to Flow's API at `https://app.flow.bio/api`, or to the
instance `FLOW_API_URL` names if you set it. When you have saved a token (see
below), the CLI sends it to that API to authenticate. File downloads use `curl`
against the same API, with the token from `~/.config/flow/api-token` in a
request header. Apart from downloading `flowbio` from PyPI, nothing is sent
anywhere else.

Every change on Flow (creating a project, editing a sample, running a pipeline,
uploading) is shown to you and runs only after you confirm it.

The launcher is a POSIX shell script, so the skill needs macOS or Linux (or
WSL on Windows).

## Getting a Flow API key (optional)

The skill works unauthenticated, but most resources on Flow are private,
so an authenticated key dramatically broadens what you can ask about.

1. Sign in to Flow at <https://app.flow.bio>.
2. Open <https://app.flow.bio/settings> and go to the **Account Management** tab.
3. In the **API Keys** section, choose:
   - **Key purpose:** *AI Agent* (recommended for use with this skill).
   - **Lifetime:** how long the key should remain valid.
4. Click create, then **copy the key immediately** — it's shown only
   once.
5. Save it to `~/.config/flow/api-token` with restrictive permissions (if on Windows see note further down):

   ```sh
   mkdir -p ~/.config/flow
   umask 077
   pbpaste > ~/.config/flow/api-token   # or paste manually
   chmod 600 ~/.config/flow/api-token
   ```

   Or set `FLOW_API_TOKEN` to the key instead; it takes precedence over the file.

The skill checks for this file on every invocation. When present, the
`flowbio` CLI reads it and authenticates every read, write, pipeline run and
upload; when absent, reads fall back to public/anonymous access. **The skill
never prints the token** — the CLI reads the file itself, and the only command
that references it directly (the file-download `curl`) does so via
`$(< ~/.config/flow/api-token)` inside a `-H` flag.

### If on Windows
<details>
<summary>Click to expand</summary>

Add the token to your windows home folder like so:

```
  New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\flow"
  [System.IO.File]::WriteAllText(
    "$env:USERPROFILE\.config\flow\api-token",
    "your-token-here"
  )
```
</details>

## Reducing permission prompts

The CLI resolves your token itself, so read commands carry no secret and can be
allowlisted. To stop reads prompting, add both entries to
`.claude/settings.json`: the read recipes pipe through `jq`, and Claude Code
only auto-approves a piped command when every part of it is allowed.

```json
{
  "permissions": {
    "allow": [
      "Bash(flow-cli api get *)",
      "Bash(jq *)"
    ]
  }
}
```

The entries stay the same from one release to the next.

Do **not** allowlist `api post` or `api patch`. Those create and edit
records and run pipelines, and the prompt is the last check that the change is
the one you confirmed.

File downloads still use `curl` and keep prompting; that is deliberate — a
download can be large.

## License

[MIT](https://github.com/goodwright/flow-skills/blob/main/LICENSE) — © 2026 Goodwright.
