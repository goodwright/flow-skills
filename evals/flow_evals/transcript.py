"""What an agent did and said, read from its `claude -p` stream-json transcript."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

_API_GET_PATH = re.compile(r"\bapi\s+get\s+(/[^\s;|&)]*)")
# A flowbio subcommand other than `api get` changes remote state; flags such as --version do not.
_FLOWBIO_WRITE = re.compile(r"\bflowbio\s+(?!api\s+get\b)[a-z]")
_CURL_WRITE = re.compile(r"\bcurl\b.*(-X\s*(POST|PUT|PATCH|DELETE)\b|\s(-d|--data\S*|-F|--form)\s)")


@dataclass(frozen=True)
class Transcript:
    answer: str
    commands: list[str]
    flow_paths: list[str]
    write_calls: list[str]
    input_tokens: int
    output_tokens: int
    turns: int


def read_transcript(path: Path) -> Transcript:
    events = _events(path)
    commands = [
        block["input"]["command"]
        for event in events if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use" and block.get("name") == "Bash"
    ]
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    usage = result.get("usage", {})
    return Transcript(
        answer=result.get("result") or "",
        commands=commands,
        flow_paths=[p for c in commands for p in _API_GET_PATH.findall(c)],
        write_calls=[c for c in commands if _FLOWBIO_WRITE.search(c) or _CURL_WRITE.search(c)],
        input_tokens=sum(usage.get(k, 0) for k in
                         ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        output_tokens=usage.get("output_tokens", 0),
        turns=result.get("num_turns", 0),
    )


def _events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
