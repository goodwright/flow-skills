# Reading the sources

How to read GEO, ENA, ArrayExpress, PubMed and Europe PMC, and the quirks of
each. Every read goes through `fetch`, by its full path:

```bash
${CLAUDE_SKILL_DIR}/scripts/fetch 'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE215250&targ=self&form=text&view=brief'
```

- `fetch` takes exactly one https URL on `www.ncbi.nlm.nih.gov`,
  `eutils.ncbi.nlm.nih.gov`, `ftp.ncbi.nlm.nih.gov`, `www.ebi.ac.uk` or
  `ftp.ebi.ac.uk`, and nothing else. It reads with plain GET: put every query
  parameter in the URL.
- **Single-quote the URL.** Unquoted, the shell trips on `?` and `&`.
- **Percent-encode spaces and `"`** in a query: `%20`, `%22`. Brackets can be
  written as they are (`GSE215250[ACCN]`).
- Shape what comes back with `grep`, `zcat`, `head` and `jq` only: they run
  without prompting the user, other tools do not.
- `fetch` does not follow redirects. A failed read says so on stderr and exits
  non-zero: report the source as **not read**, never as "nothing found". An
  empty answer with no error is usually a redirect: find the direct link as
  below.

## Search order

For an attribute, look in this order, unless its guidance says otherwise:

1. The paper's Methods, for the assay the sample comes from.
2. The paper's Key Resources table, if it has one.
3. The GEO sample records (characteristics, source name, extraction protocol),
   or the ArrayExpress SDRF.
4. The ENA records.
5. Supplementary files.

The first source that states a value is the quote; a later one that disagrees
is shown beside it.

## GEO

**Never read GEO's HTML accession page.** It sits behind a reCAPTCHA and
answers with a challenge page that reads as "not found". Read the SOFT text
instead:

| What | URL |
|---|---|
| The series: title, status, PubMed id, its samples | `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=<GSE>&targ=self&form=text&view=brief` |
| Every sample of the series, in one read | `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=<GSE>&targ=gsm&form=text&view=brief` |
| The series matrix (gzipped) | list `https://ftp.ncbi.nlm.nih.gov/geo/series/<GSEnnn>/<GSE>/matrix/` first, then read the file it names with `\| zcat`: `<GSE>_series_matrix.txt.gz`, or one `<GSE>-GPL<n>_series_matrix.txt.gz` per platform |
| A series' supplementary files | `https://ftp.ncbi.nlm.nih.gov/geo/series/<GSEnnn>/<GSE>/suppl/` |

`<GSEnnn>` is the accession with its last three digits replaced by `nnn`
(`GSE215250` → `GSE215nnn`). GEO's own links to these files start `ftp://`:
rewrite them to `https://ftp.ncbi.nlm.nih.gov/…`.

- **Released or not.** A released series answers in SOFT (lines starting `^`
  and `!`) and says `!Series_status = Public on <date>`. An embargoed one
  answers in HTML. Judge by the format, not by searching the text for
  "private".
- **Experiment accessions.** Each sample's `!Sample_relation = SRA:` line ends
  in its `SRX`.
- **Characteristics.** `!Sample_characteristics_ch1 = <key>: <value>` lines
  hold cell line, tissue, genotype and the like; `!Sample_source_name_ch1` is
  often a loose description, not a cell line.
- **PubMed id.** `!Series_pubmed_id` can name the wrong paper: check its title
  (below) against the series title.

To find the series for a paper, ask E-utilities for the GEO records linked
to it, then read each record's `accession`:

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&db=gds&id=<PMID>&retmode=json
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gds&id=<uid>,<uid>&retmode=json
```

The links include a SuperSeries beside its SubSeries, and its samples are
theirs: pick the SubSeries for the assay the user means. An `elink` with no
links does not mean there is no series: GEO links a series only to the paper
its submitter named, so fall back on the paper's Data Availability text,
which names its accessions.

## ENA

The filereport resolves a BioProject, a study, an experiment or a run to its
runs, one row per run, each with the experiment it belongs to:

```
https://www.ebi.ac.uk/ena/portal/api/filereport?accession=<accession>&result=read_run&fields=run_accession,experiment_accession,sample_accession,sample_title,library_layout,library_strategy&format=tsv
```

- A run accession (`SRR`, `ERR`, `DRR`) resolves to its `experiment_accession`
  here. Import the experiment.
- An accession that is not released returns no rows, or an error, rather than
  its runs. Say so; do not guess from the accession's format.
- `library_strategy` is how the submitter filed the library, not what the
  assay was: read the experimental method from the protocol text instead.

## ArrayExpress

ArrayExpress series (`E-MTAB-…`) live in BioStudies. Its `/info` names the
study's file location:

```
https://www.ebi.ac.uk/biostudies/api/v1/studies/<E-MTAB>/info
```

Read the SDRF from `<httpLink>/Files/<E-MTAB>.sdrf.txt`, where `httpLink`
comes from that answer (on `ftp.ebi.ac.uk`). The `www.ebi.ac.uk` file links
redirect there, and `fetch` does not follow redirects. In the SDRF,
`Comment[ENA_EXPERIMENT]` is the experiment accession,
`Comment[SUBMITTED_FILE_NAME]` the submitter's filename, and `Factor Value[…]`
and `Characteristics[…]` columns the curated metadata.

## PubMed and Europe PMC

Find a paper, its PMCID and whether its full text is open:

```
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>%20AND%20SRC:MED&format=json&resultType=lite
```

To find a paper from its title, search `query=TITLE:(<word>%20AND%20<word>)`
the same way, with a few distinctive words of the title; a quoted phrase,
`TITLE:%22<words>%22`, matches only words that sit together in it. A result
without a `pmid` is a preprint: prefer the published paper.

- **Methods text.** For an open-access paper (`isOpenAccess` `Y`), read
  `https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML` and
  `grep` for the assay's section. A paper without open full text has no
  Methods you can read: say so, and use what the user pastes from it as a
  quoted source.
- **Supplementary files.**
  `https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/supplementaryFiles`
  answers with a zip archive, which you cannot unpack, and PMC's own
  supplementary downloads sit behind a challenge. Report such a file as
  **not read** and name it, so the user can open it themselves.
