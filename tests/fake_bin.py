import shutil
from pathlib import Path


def fake_bin(tmp_path: Path, *names: str, real_tools: tuple[str, ...] = ()) -> Path:
    """A PATH of tools that each print their own name and arguments, beside the real tools a script needs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in real_tools:
        (bin_dir / tool).symlink_to(shutil.which(tool))
    for name in names:
        tool = bin_dir / name
        tool.write_text(f'#!/bin/sh\necho "{name} $*"\n')
        tool.chmod(0o755)
    return bin_dir
