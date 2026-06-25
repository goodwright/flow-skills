# flow-skills

Agent skills for [Flow](https://flow.bio), a bioinformatics platform
built by [Goodwright](https://goodwright.com). This repository is a
plugin marketplace; today it ships one plugin, **`flow-ai`**, which
lets an AI agent query Flow's REST API — and upload data — on
your behalf.

## What `flow-ai` does

`flow-ai` is primarily a read-only skill that can also upload data to
Flow: generic data files, demultiplexed samples, and multiplexed reads
with an annotation sheet. With it, an agent can answer questions and run
uploads like:

- "What pipelines are available on Flow?"
- "How many samples do I own?"
- "What was the last successful execution of the RNA-Seq pipeline on
  sample X, and what data files did it produce?"
- "Download the FASTQ for data file 67890."
- "Upload counts.tsv to Flow as a data file."
- "Upload a paired-end RNA-Seq sample with this metadata."
- "Upload these multiplexed reads with my annotation sheet."

See [`plugins/flow-ai/skills/flow-ai/SKILL.md`](plugins/flow-ai/skills/flow-ai/SKILL.md)
for the current capabilities.

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

The skill checks for this file on every invocation. When present, it
attaches `Authorization: Bearer …` to every request. When absent, it
proceeds unauthenticated. **The skill never prints the token** — it's
referenced only via `$(< ~/.config/flow/api-token)` inside a `curl -H`
flag.

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



## Install — Claude Code (recommended)

This repo is a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).
Inside Claude Code:

```text
/plugin marketplace add goodwright/flow-skills
/plugin install flow-ai@flow-skills
```

To pick up new releases later, run `/plugin marketplace update`.

## Install — other agents

The skill itself is just a directory of Markdown files following
[Anthropic's Agent Skill format](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview).
Any agent harness that loads skills from a directory can use it
directly. Clone the repo and point your harness at
`plugins/flow-ai/skills/flow-ai/`:

```sh
git clone https://github.com/goodwright/flow-skills.git
# Then either symlink or copy plugins/flow-ai/skills/flow-ai/ into wherever
# your agent loads skills from. For example, for Claude Code's standalone
# mode:
mkdir -p ~/.claude/skills
ln -s "$(pwd)/flow-skills/plugins/flow-ai/skills/flow-ai" ~/.claude/skills/flow-ai
```

For agents that consume `SKILL.md` directly (Codex, Gemini CLI,
Copilot CLI, etc.), see your harness's documentation for the skill
load path. The skill's contract is the YAML frontmatter in `SKILL.md`
plus the supporting files it references — no harness-specific glue.

## Versioning

The canonical version lives in
[`plugins/flow-ai/.claude-plugin/plugin.json`](plugins/flow-ai/.claude-plugin/plugin.json).
The `User-Agent: flow-ai/<version>` string in `SKILL.md` is kept in
lockstep so Flow's backend can attribute traffic to a specific release.
On each release, bump:

1. `plugins/flow-ai/.claude-plugin/plugin.json#version`
2. The `User-Agent` strings in `SKILL.md` and `examples.md`
3. `CHANGELOG.md`

A pre-release sanity check:

```sh
grep -rn "flow-ai/" plugins/flow-ai/skills/flow-ai/ | grep -v 0.2.0
```

…should return nothing once everything is in lockstep.

## Contributing

Issues and PRs welcome at
<https://github.com/goodwright/flow-skills>. For changes to the skill
itself, also update an eval (or add a new one) that demonstrates the
new behaviour.

## License

[MIT](LICENSE) — © 2026 Goodwright.
