import re
import shutil
import subprocess
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "flowbio"
LAUNCHER = PLUGIN / "skills" / "flow-assistant" / "scripts" / "flow-cli"
# The launcher's only external tool. PATH holds just it and the fakes, so a uvx,
# pipx or flowbio installed on the machine, as pipx is in /usr/bin on Ubuntu, never answers.
SCRIPT_TOOLS = ["cat"]


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


def _run(command: Path, bin_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(command), *(args or ("api", "get", "/me", "--json"))], capture_output=True,
                          text=True, env={"PATH": str(bin_dir)})


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


@pytest.mark.parametrize("option", [
    ["--base-url", "https://elsewhere.example"], ["--base-url=https://elsewhere.example"], ["--base", "x"],
    ["--token", "x"], ["--tok=x"], ["--token-file", "/etc/hosts"], ["--token-f=/etc/hosts"],
])
def test_refuses_options_that_redirect_the_request_or_its_credential(tmp_path, option):
    result = _run(LAUNCHER, _fake_bin(tmp_path, "uvx"), "api", "get", "/me", *option, "--json")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "app.flow.bio" in result.stderr and "FLOW_API_URL" not in result.stderr


@pytest.mark.parametrize("option", [["--body", "-"], ["--param", "base_url=x"], ["--no-progress"]])
def test_passes_other_options_through(tmp_path, option):
    result = _run(LAUNCHER, _fake_bin(tmp_path, "uvx"), "api", "get", "/me", *option)
    assert result.stdout.strip().endswith(" ".join(["/me", *option]))


def test_the_skill_pre_approves_only_reads_through_the_launcher():
    # Widening this rule, say to `flow-cli *`, would let writes and uploads run without the user's confirmation.
    skill = (LAUNCHER.parents[1] / "SKILL.md").read_text()
    allowed = re.search(r"^allowed-tools: (.+)$", skill, re.MULTILINE).group(1)
    assert allowed == "Bash(${CLAUDE_SKILL_DIR}/scripts/flow-cli api get *) Bash(jq *)"


def _run_with_api_url(tmp_path: Path, api_url: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(LAUNCHER), "api", "get", "/me", "--json"], capture_output=True, text=True,
                          env={"PATH": str(_fake_bin(tmp_path, "uvx")), "FLOW_API_URL": api_url})


@pytest.mark.parametrize("api_url", [
    "https://staging.flow.bio/api", "https://elsewhere.example/api", "http://localhost.elsewhere.example/api",
    "http://127.0.0.1.elsewhere.example/api", "http://localhost:8019@elsewhere.example/api",
    "http://127.0.0.1:@elsewhere.example",
])
def test_refuses_a_flow_api_url_off_this_machine(tmp_path, api_url):
    result = _run_with_api_url(tmp_path, api_url)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "FLOW_API_URL" in result.stderr


@pytest.mark.parametrize("api_url", ["http://localhost", "http://localhost:8019", "http://127.0.0.1:8019/api"])
def test_uses_a_flow_api_url_on_this_machine(tmp_path, api_url):
    result = _run_with_api_url(tmp_path, api_url)
    assert result.returncode == 0
    assert result.stdout.startswith("uvx ")


def test_ignores_variables_inherited_from_the_environment(tmp_path):
    bin_dir = _fake_bin(tmp_path, "uvx")
    result = subprocess.run([str(LAUNCHER), "api", "get", "/me", "--json"], capture_output=True, text=True,
                            env={"PATH": str(bin_dir), "refused": "x", "option": "--base-url"})
    assert result.returncode == 0
