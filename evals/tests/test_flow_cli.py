import re
import shutil
import subprocess
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "flow-ai"
LAUNCHER = PLUGIN / "skills" / "flow-ai" / "scripts" / "flow-cli"
SHIM = PLUGIN / "bin" / "flow-cli"
# The scripts' only external tools. PATH holds just these and the fakes, so a uvx,
# pipx or flowbio installed on the machine, as pipx is in /usr/bin on Ubuntu, never answers.
SCRIPT_TOOLS = ["cat", "dirname"]


def _pinned_version() -> str:
    return re.search(r'^FLOWBIO_VERSION=(\S+)$', LAUNCHER.read_text(), re.MULTILINE).group(1)


def _fake_bin(tmp_path: Path, *names: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in SCRIPT_TOOLS:
        (bin_dir / tool).symlink_to(shutil.which(tool))
    for name in names:
        tool = bin_dir / name
        tool.write_text(f'#!/bin/sh\necho "{name} $*"\n')
        tool.chmod(0o755)
    return bin_dir


def _run(command: Path, bin_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(command), "api", "get", "/me", "--json"], capture_output=True, text=True,
                          env={"PATH": str(bin_dir)})


def test_uses_uvx_with_the_pinned_version_first(tmp_path):
    result = _run(LAUNCHER, _fake_bin(tmp_path, "uvx", "pipx", "flowbio"))
    assert result.stdout.strip() == f"uvx --from flowbio=={_pinned_version()} flowbio api get /me --json"


def test_falls_back_to_pipx_with_the_pinned_version(tmp_path):
    result = _run(LAUNCHER, _fake_bin(tmp_path, "pipx", "flowbio"))
    assert result.stdout.strip() == f"pipx run --spec flowbio=={_pinned_version()} flowbio api get /me --json"


def _install_flowbio(bin_dir: Path, version: str) -> None:
    flowbio = bin_dir / "flowbio"
    flowbio.write_text(f'#!/bin/sh\n[ "$1" = --version ] && echo "flowbio {version}" && exit\necho "flowbio $*"\n')
    flowbio.chmod(0o755)


def test_falls_back_to_an_installed_flowbio_at_the_pinned_version(tmp_path):
    bin_dir = _fake_bin(tmp_path)
    _install_flowbio(bin_dir, _pinned_version())
    result = _run(LAUNCHER, bin_dir)
    assert result.stdout.strip() == "flowbio api get /me --json"


def test_refuses_an_installed_flowbio_at_another_version(tmp_path):
    pinned = _pinned_version()
    installed = pinned + "0"
    bin_dir = _fake_bin(tmp_path)
    _install_flowbio(bin_dir, installed)
    result = _run(LAUNCHER, bin_dir)
    assert result.returncode == 127
    assert result.stdout == ""
    assert installed in result.stderr and f"flowbio=={pinned}" in result.stderr


def test_refuses_an_installed_flowbio_that_does_not_run(tmp_path):
    bin_dir = _fake_bin(tmp_path)
    (bin_dir / "flowbio").write_text("#!/bin/sh\necho ModuleNotFoundError >&2\nexit 1\n")
    (bin_dir / "flowbio").chmod(0o755)
    result = _run(LAUNCHER, bin_dir)
    assert result.returncode == 127
    assert "doesn't run" in result.stderr and f"flowbio=={_pinned_version()}" in result.stderr


def test_without_any_runner_says_what_to_install(tmp_path):
    result = _run(LAUNCHER, _fake_bin(tmp_path))
    assert result.returncode == 127
    assert result.stdout == ""
    assert "uv" in result.stderr and f"flowbio=={_pinned_version()}" in result.stderr


def test_passes_on_the_exit_code(tmp_path):
    bin_dir = _fake_bin(tmp_path)
    (bin_dir / "uvx").write_text("#!/bin/sh\nexit 3\n")
    (bin_dir / "uvx").chmod(0o755)
    assert _run(LAUNCHER, bin_dir).returncode == 3


def test_the_plugin_command_runs_the_skill_launcher(tmp_path):
    bin_dir = _fake_bin(tmp_path, "uvx")
    assert _run(SHIM, bin_dir).stdout == _run(LAUNCHER, bin_dir).stdout
