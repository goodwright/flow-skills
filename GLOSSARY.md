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
A request the agent makes to Flow that the runner counts: a CLI `api get` in skill mode, any Flow MCP tool call in MCP mode.

**Write call**:
Anything the agent does that can change Flow's state: a CLI command other than `api get`, a mutating `curl`, or a call to a Flow MCP tool not marked read-only.
_Avoid_: mutation
