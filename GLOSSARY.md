# Flow skills

Agent skills and plugins that let an AI agent work with Flow, and the evals that measure how well an agent does.

## Evals

**Scenario**:
One question put to an agent, with the rubric and checks its answer is graded on.

**Mode**:
How the agent under test reaches Flow during an eval run: skill mode or MCP mode.
_Avoid_: transport, variant

**Skill mode**:
The agent reaches Flow through the flowbio plugin's skill and its CLI.

**MCP mode**:
The agent reaches Flow only through Flow's MCP server.

**Flow call**:
One request the agent makes to Flow: a CLI `api get` in skill mode, a Flow MCP tool call in MCP mode.

**Write call**:
A Flow call that can change Flow's state: any CLI command other than a read, or a Flow MCP tool not marked read-only.
_Avoid_: mutation
