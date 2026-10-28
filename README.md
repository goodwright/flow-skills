# flow-skills

Agent skills for [Flow](https://flow.bio), a bioinformatics platform
built by [Goodwright](https://goodwright.com). This repository is a
plugin marketplace; today it ships one plugin, **`flowbio`**, which
lets an AI agent query Flow's REST API — and upload data — on
your behalf.

## What `flowbio` does

The plugin's [README](plugins/flowbio/README.md) says what it does, what it
runs and sends, and how to reduce permission prompts.

## Getting a Flow API key (optional)

See [Getting a Flow API key](plugins/flowbio/README.md#getting-a-flow-api-key-optional)
in the plugin's README.

## Install — Claude Code (recommended)

This repo is a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).
Inside Claude Code:

```text
/plugin marketplace add goodwright/flow-skills
/plugin install flowbio@flow-skills
```

To pick up new releases later, run `/plugin marketplace update`.

## Install — other agents

The skill itself is just a directory of Markdown files following
[Anthropic's Agent Skill format](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview).
Any agent harness that loads skills from a directory can use it
directly. Clone the repo and point your harness at
`plugins/flowbio/skills/flow-assistant/`:

```sh
git clone https://github.com/goodwright/flow-skills.git
# Then either symlink or copy plugins/flowbio/skills/flow-assistant/ into wherever
# your agent loads skills from. For example, for Claude Code's standalone
# mode:
mkdir -p ~/.claude/skills
ln -s "$(pwd)/flow-skills/plugins/flowbio/skills/flow-assistant" ~/.claude/skills/flow-assistant
```

For agents that consume `SKILL.md` directly (Codex, Gemini CLI,
Copilot CLI, etc.), see your harness's documentation for the skill
load path. The skill's contract is the YAML frontmatter in `SKILL.md`
plus the supporting files it references — no harness-specific glue.

Installed this way, without the plugin, `flow-cli` is not on your `PATH`; the
skill runs its copy at `scripts/flow-cli` in the skill's directory instead.

## Versioning

The canonical version lives in
[`plugins/flowbio/.claude-plugin/plugin.json`](plugins/flowbio/.claude-plugin/plugin.json).
On each release, bump it and add the release to `CHANGELOG.md`.

The `flowbio` version the skill runs is pinned in one place,
`FLOWBIO_VERSION` in
[`plugins/flowbio/skills/flow-assistant/scripts/flow-cli`](plugins/flowbio/skills/flow-assistant/scripts/flow-cli).
To move to a new `flowbio`, change it there.

## Contributing

Issues and PRs welcome at
<https://github.com/goodwright/flow-skills>. For changes to the skill
itself, also update an eval (or add a new one) that demonstrates the
new behaviour, and add a `CHANGELOG.md` entry under the next version (or
`[Unreleased]`) for anything a user would notice.

Skills in `unpublished/` are kept for later work and are not part of any
plugin, so no install picks them up.

Don't add `allowed-tools` to the skill's frontmatter: with it, Claude Code
invoked the skill without passing its text to the model, which then guessed
at commands.

## License

[MIT](LICENSE) — © 2026 Goodwright.
