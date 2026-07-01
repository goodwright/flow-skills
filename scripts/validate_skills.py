#!/usr/bin/env python3
"""Validate skill frontmatter before install.

The plugin installer rejects a SKILL.md whose `description` exceeds 1024
characters. This catches that (and a missing name/description) in CI.
"""
import glob
import sys

MAX_DESCRIPTION = 1024


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else None


def field(block, key):
    """Value of a single-line `key:` in the frontmatter block, or None."""
    prefix = key + ":"
    for line in block.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def check(path):
    with open(path, encoding="utf-8") as f:
        block = frontmatter(f.read())
    if block is None:
        return [f"{path}: missing YAML frontmatter"]

    errors = []
    name = field(block, "name")
    description = field(block, "description")

    if not name:
        errors.append(f"{path}: frontmatter is missing `name`")
    if not description:
        errors.append(f"{path}: frontmatter is missing `description`")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(
            f"{path}: description is {len(description)} chars "
            f"(max {MAX_DESCRIPTION})"
        )
    return errors


def main():
    paths = sorted(glob.glob("plugins/**/SKILL.md", recursive=True))
    if not paths:
        print("No SKILL.md files found under plugins/", file=sys.stderr)
        return 1

    errors = [e for path in paths for e in check(path)]
    for e in errors:
        print(e, file=sys.stderr)
    print(f"Checked {len(paths)} skill(s), {len(errors)} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
