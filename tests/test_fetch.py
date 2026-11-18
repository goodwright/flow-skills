import subprocess
from pathlib import Path

import pytest

from fake_bin import fake_bin

FETCH = (Path(__file__).resolve().parents[1] / "plugins" / "flowbio" / "skills" / "public-sample-curation"
         / "scripts" / "fetch")
GEO_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE215250&targ=self&form=text&view=brief"


def _fetch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Runs fetch with a curl that prints its arguments, so no request leaves the machine."""
    return subprocess.run([str(FETCH), *args], capture_output=True, text=True,
                          env={"PATH": str(fake_bin(tmp_path, "curl"))})


@pytest.mark.parametrize("url", [
    GEO_URL,
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gds&term=GSE1",
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE215nnn/GSE215250/matrix/",
    "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJNA889426&result=read_run",
    "https://ftp.ebi.ac.uk/biostudies/fire/E-MTAB-/001/E-MTAB-1001/Files/E-MTAB-1001.sdrf.txt",
])
def test_reads_a_url_on_each_allowed_host_ignoring_curlrc_and_showing_errors(tmp_path: Path, url: str) -> None:
    fetched = _fetch(tmp_path, url)
    assert (fetched.returncode, fetched.stdout) == (0, f"curl -q -sS -g {url}\n")


def test_reads_a_url_with_brackets_or_braces_as_the_one_url_it_is(tmp_path: Path) -> None:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db={gds,pubmed}&term=GSE1[ACCN]"
    assert _fetch(tmp_path, url).stdout == f"curl -q -sS -g {url}\n"


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
def test_refuses_anything_but_one_url_on_an_allowed_host(tmp_path: Path, args: list[str]) -> None:
    fetched = _fetch(tmp_path, *args)
    assert (fetched.returncode, fetched.stdout) == (2, "")
    assert "fetch:" in fetched.stderr
