# 5' Barcode Sequence

**What it means.** The sequence at the 5' end of each read that the library
adds before the insert: its random positions (the UMI) and any fixed bases
that identify the sample, as one pattern, for example `NNNCGGANNN`.

**How Flow records it.** Upper case, as the read carries it. A random position
is `N`; so is any degenerate code (`R`, `Y`, `B` and the rest) and a
placeholder such as `X`, since only `A`, `C`, `G`, `T` and `U` name a fixed
base.

Each sample takes its own library's barcode. A sample of an assay with no 5'
barcode, such as an RNA-Seq library beside the CLIP ones, is left empty.

**Never claim to have checked a barcode against the reads.** Sequencing data
is not read here, so a barcode stands on what the sources state.

## Where to look

1. The series matrix: `!Sample_extract_protocol_ch1` and
   `!Sample_data_processing`, each sample's protocol and processing text,
   which sometimes state the barcode or its length.
2. **The paper's Methods, for the CLIP assay only.** Methods often describe
   several barcoding schemes; a pattern from an RNA-Seq or RIP section is not
   this library's.
3. Supplementary material, as a last pass: oligo and adapter tables, the Key
   Resources table, the authors' demultiplexing config, and the filenames in
   each sample's `!Sample_supplementary_file_1`, which often carry its
   barcode's fixed core.

**A stated barcode may be the RT primer, not the read.** The read carries the
primer's reverse complement, which also swaps the random lengths on either
side: a primer written `NN XXXX NNN` reads as `NNN revcomp(XXXX) NN`. When the
source says it gives the primer, propose the read form, inferred, with the
reasoning.

## Several barcodes, one per replicate

When the paper lists several patterns, each replicate has one of them. Find
which from the fixed core each sample carries, most often in its
supplementary filenames. The value is **inferred**: quote the paper's
sentence and each sample's filename with their URLs, and flag the mapping for
the user to confirm.

When no source shows which replicate has which pattern, never assign the
paper's patterns by guess, and never give every replicate one of them. Propose
each replicate the all-`N` pattern of the patterns' length as inferred, list
the paper's patterns, and flag that the mapping is unknown.

## Lengths without a motif

A source may give only lengths. Propose the all-`N` pattern of the length the
text supports as **inferred**, quote the sentence, and flag it: a library can
carry fixed bases that a length leaves out, so the user confirms it.

## An eCLIP library

When an eCLIP study states no randomer, propose `NNNNNNNNNN`, the 10 nt
randomer of the standard eCLIP protocol, as inferred, with that reason. An
eCLIP sample's `inline barcodes:` name demultiplexing adapters on the other
read, not this barcode.

## No barcode found

When nothing above gives a pattern or a length, leave the barcode empty and
say what was searched. A CLIP sample needs one, so flag the sample as
unimportable until the user gives it.

## Worked examples

- **GSE105082 (DHX9 iCLIP):** the paper's Methods say "Barcodes
  (NNNCGGANNN and NNNGGCANNN) were used for demultiplexing". GEO's
  supplementary filenames carry each replicate's core:
  `GSM2817677_rsem_CGGA…` for iCLIP-DHX9-1, so `NNNCGGANNN`, and
  `GSM2817678_rsem_GGCA…` for iCLIP-DHX9-2, so `NNNGGCANNN`. Both inferred
  from the two together, and flagged.
- **GSE303135 (hnRNPH iCLIP2):** GEO's data processing gives only "first 15
  bp" and "15 bp barcode and UMI regions" within a 30 bp minimum, so the text
  supports 15 `N`, inferred and flagged. The library in fact carries a fixed
  `ACATCG` at positions 6 to 11 (`NNNNNACATCGNNNN`), which no source states:
  the reason a length-only barcode is always the user's to confirm.
