---
name: public-sample-curation
description: Use when someone wants the samples of a published study on Flow (flow.bio) with their metadata worked out from the study — from a paper, a GEO or ArrayExpress series, a BioProject or a list of accessions. Finds the study, checks its data is released, resolves it to experiment accessions, and proposes each sample's metadata with the source of every value for the user to approve; flow-assistant then imports what they approved. An import where the user already gives every value is flow-assistant's alone.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/fetch *) Bash(grep *) Bash(zcat *) Bash(head *) Bash(jq *) Write(./*.tsv)
---

# Public sample curation

Take the user from "the samples in this study" to samples on Flow whose
metadata they have checked. You do the curation: find the study, resolve its
samples to experiment accessions, and propose a value for every attribute Flow
records, each with where it came from. Every Flow read and the import itself go
through the **flow-assistant** skill: load it (`flowbio:flow-assistant`) before
the first Flow read and follow its rules for every call to Flow. Never reach
Flow any other way.

**Execute every command yourself with the bash tool.** Never hand the user a
command to run or a plan of steps. Keep going until you have a proposal to show.

## The evidence rule

Every value you propose has one of three statuses, and the review shows which:

- **quoted** — a named source states it. Show the exact text and the URL you
  read it from: a GEO field, an SDRF column, a sentence of the paper, a row of
  a supplementary table. A quote without its URL is not quoted.
- **inferred** — no source states it, but the evidence and general knowledge
  support it. Show your reasoning and flag the value for the user to confirm.
- **empty** — nothing supports a value. Leave it blank and say what you searched.

**A value you cannot quote is never filled to look complete.** Empty is a
correct answer; a plausible value with no source is the failure this skill
exists to prevent.

For an attribute with options (`has_options`), look each candidate up through
flow-assistant with the attribute's `/options` and `value=<substring>`. Never
list a long option set whole.

- An option that names the same thing is the value: an alias resolves to its
  gene symbol (`PARP13` → `ZC3HAV1`), shown as **inferred** with the reason.
- If no option fits and the attribute allows user terms (`allow_user_terms`),
  propose the study's term and flag it in the review as a **new term**: Flow
  will store it as an unvalidated option. Do the same for a term an
  attribute's guidance names. Never pick the nearest option instead.
- If no option fits and user terms are not allowed, leave it **empty** and say
  so.

An attribute that takes an annotation (`allow_annotation`) gets one by the
same rule: propose it when a source supports it, and leave it empty otherwise.

**When sources disagree, show both.** Quote each, propose the one the evidence
supports, and flag it for the user. A PubMed id is checked against its paper:
the paper's title must describe the series. GEO records sometimes link the
wrong paper.

## Workflow

### 1. Resolve the study

From whatever the user gave you, find the samples and their **experiment**
accessions (`SRX`, `ERX`, `DRX`). `sources.md` says how to read each source.

- A run accession (`SRR`, `ERR`, `DRR`) is resolved to its experiment through
  ENA's filereport before anything else.
- One sample per distinct experiment accession: an experiment with several
  runs appears once, and Flow refuses an import that names one twice.
- **Check the data is released.** An embargoed accession looks like a real
  one, and a paper's Data Availability statement is a promise, not a fact. If
  it is not released, stop and say so, with the release date if the source
  gives one.
- When the series mixes assays (RNA-Seq beside CLIP, say) and the user named
  some samples, keep to those.

### 2. Read the target from Flow, through flow-assistant

- The sample types, from `/v2/sample-types`. Choose each sample's type from
  the assay the study's records describe (the series design, the extraction
  protocol), not from GEO's `library_strategy`. A series that mixes assays
  can need more than one type.
- Each chosen type's attributes, from `/v2/metadata-attributes?sample_type=…`:
  each one's name, description, whether it is required, has options, allows
  user terms, and takes an annotation. **This list is what you curate.** Never
  work from a list of your own.
- The organism's `id`, from `/v2/organisms`.
- The project to import into: the one the user named. If they named none, ask.
  Never create a project. Check it is private and the user can edit it before
  you build the review: Flow imports only into such a project.

Whether these samples are already on Flow cannot be checked yet. Say so in the
review header.

### 3. Gather the evidence

Read the GEO series and sample records (or the ArrayExpress SDRF), the ENA
records, the paper's Methods and its supplementary files, in the order
`sources.md` gives. An attribute's guidance may narrow the order. A file you
could not open (a supplement behind a challenge, an archive you cannot unpack)
is reported as **not read**, never as "no evidence".

### 4. Propose values

For each attribute in the list from step 2, read
`${CLAUDE_SKILL_DIR}/attributes/<identifier>.md` if it exists and follow it.
Otherwise apply the evidence rule using the attribute's name and description
from Flow. The sample type, organism, PubMed id and sample name are proposed
the same way.

A sample name starts from the source's sample title, with spaces and symbols
replaced by `_`.

A required attribute left empty makes that sample unimportable. Say which, and
ask for a value or whether to leave the sample out.

### 5. Review

Show the proposal and ask the user to approve or correct it. The review names
everything the import will send, so it is the confirmation flow-assistant's
"Confirm before every write" asks for:

1. **A header**: the study, the target project (name and id), and what every
   sample shares: sample type (identifier), organism (`id`), PubMed id. A value
   goes here only when every sample has it; otherwise it gets its own section.
   Then the line "Not checked: whether these samples are already on Flow."
2. **One section per attribute**, inferred, empty and new-term values first.
   For each distinct value: the value and any annotation exactly as they will
   be sent, which samples have it, its status, and its source: the quote and
   its URL, the reasoning, or for an empty value what you searched and any file
   you could not read.
3. **The samples**: each sample's name and experiment accession.

Above about 20 samples, also write the full per-sample table to
`<study>-proposal.tsv` in the working directory and say where it is.

Apply each correction, show the changed sections again, and ask again. **Import
nothing until the user approves the proposal as it stands.** A correction is
not an approval.

### 6. Hand off

On an explicit yes, have flow-assistant import the approved samples as
`GET /v2/reference/sample-imports` describes, with exactly the values the
review showed, and without asking again: the user's yes to the review is the
confirmation. An inferred value the user approved is the user's value. Then
follow the import to its end and report it, as flow-assistant does.
