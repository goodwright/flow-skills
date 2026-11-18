# 5' Barcode Sequence

**What it means.** The sequence at the 5' end of each read that the library
adds before the insert: the random positions (the UMI) and any fixed bases
that demultiplex the samples, as one pattern, for example `NNNCGGANNN`.

**How Flow records it.** A string of `A`, `C`, `G`, `T`, `U`, `N` and `-`.
Write a random position as `N`, and turn any other IUPAC code (`R`, `Y`, `B`
and the rest) into `N`: the replicate a pattern belongs to is carried by the
sample, not by those letters. Flow refuses any other character.

## Where to look

1. The series matrix: `!Sample_extract_protocol_ch1` and
   `!Sample_data_processing` sometimes state the barcode.
2. **The paper's Methods, for the CLIP assay only.** Methods often describe
   several barcoding schemes; a pattern from an RNA-Seq or RIP section is not
   this library's.
3. GEO's sample *Data processing* field, which can carry the trimming detail
   when the series says only "refer to associated publication".
4. Supplementary material, as a last pass: oligo and adapter tables, the
   Key Resources table, the authors' demultiplexing config, and **GEO's
   supplementary filenames**, which often carry each sample's barcode core.

## Several barcodes, one per replicate

When the paper lists several patterns, each replicate has one of them. Find
which from the fixed core each sample carries, most often in its
supplementary filenames. Show the paper's sentence and the filename together
as the evidence. A study where every replicate gets the same pattern
demultiplexes each replicate into the others' reads with no error, so never
give them all one pattern for want of the mapping.

## Lengths without a motif

A source may give only lengths ("first 15 bp", "15 bp barcode and UMI regions
plus 15 bp sequence insert" within a 30 bp minimum). Propose the all-`N`
pattern of the length the text supports, here 15 `N`, as **inferred**: quote
the sentence and give your reading of it. A barcode cannot be checked against
the reads: its random positions and the UMI show no boundary in the sequence,
so never claim to have checked one.

## Partial evidence

When one sample lacks what its siblings have, propose for it the all-`N`
pattern of its siblings' length as **inferred**, with that reasoning. Do not
hold back the study's other samples.

## Worked examples

- **GSE105082 (DHX9 iCLIP):** the paper's Methods say "Barcodes
  (NNNCGGANNN and NNNGGCANNN) were used for demultiplexing". GEO's
  supplementary filenames carry each replicate's core:
  `GSM2817677_rsem_CGGA…` for iCLIP-DHX9-1, so `NNNCGGANNN`, and
  `GSM2817678_rsem_GGCA…` for iCLIP-DHX9-2, so `NNNGGCANNN`.
- **GSE303135 (hnRNPH iCLIP2):** GEO's *Data processing* gives "first 15 bp"
  and "15 bp barcode and UMI regions" within 30 bp, so 15 `N`, inferred.
