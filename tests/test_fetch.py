import shutil
import subprocess
from pathlib import Path

import pytest

FETCH = (Path(__file__).resolve().parents[1] / "plugins" / "flowbio" / "skills" / "public-sample-curation"
         / "scripts" / "fetch")
GEO_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE215250&targ=self&form=text&view=brief"


def _fake_curl(tmp_path: Path) -> Path:
    """A PATH holding only a curl that echoes its arguments, so no request leaves the machine."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text('#!/bin/sh\nprintf "curl"\nprintf " %s" "$@"\n')
    curl.chmod(0o755)
    (bin_dir / "sh").symlink_to(shutil.which("sh"))
    return bin_dir


def _fetch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(FETCH), *args], capture_output=True, text=True,
                          env={"PATH": str(_fake_curl(tmp_path))})


def test_reads_a_url_on_an_allowed_host_with_curl(tmp_path):
    fetched = _fetch(tmp_path, GEO_URL)
    assert (fetched.returncode, fetched.stdout) == (0, f"curl -s {GEO_URL}")


@pytest.mark.parametrize("url", [
    "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE1&form=text",
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gds&term=GSE1",
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE215nnn/GSE215250/matrix/",
    "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJNA889426&result=read_run",
    "https://ftp.ebi.ac.uk/biostudies/fire/E-MTAB-/001/E-MTAB-1001/Files/E-MTAB-1001.sdrf.txt",
])
def test_reads_from_each_allowed_host(tmp_path, url):
    assert _fetch(tmp_path, url).stdout == f"curl -s {url}"


@pytest.mark.parametrize("args", [
    ["https://example.com/"],
    ["http://www.ncbi.nlm.nih.gov/geo/"],
    ["https://www.ncbi.nlm.nih.gov.example.com/"],
    ["https://www.ncbi.nlm.nih.gov@example.com/"],
    ["https://www.ncbi.nlm.nih.gov:8080/geo/"],
    ["https://www.ebi.ac.uk"],
    [GEO_URL, "https://example.com/"],
    [GEO_URL, "-d", "@/home/me/.config/flow/api-token"],
    ["-o", "/tmp/x", GEO_URL],
    [],
])
def test_refuses_anything_but_one_url_on_an_allowed_host(tmp_path, args):
    fetched = _fetch(tmp_path, *args)
    assert (fetched.returncode, fetched.stdout) == (2, "")
    assert "fetch:" in fetched.stderr
