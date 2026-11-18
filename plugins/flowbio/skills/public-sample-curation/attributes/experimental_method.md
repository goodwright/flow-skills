# Experimental Method

**What it means.** The published protocol the sample's library was prepared
with, as the study names it: for example `TruSeq Total Stranded RNA` for
GSE255777's RNA-Seq libraries, or the CLIP variant (`iCLIP`, `eCLIP`,
`seCLIP`, `irCLIP`, `PAR-CLIP`, `HITS-CLIP`, `iCLAP`, `uvCLAP`) for a CLIP
library.

**How Flow records it.** As the protocol is usually written.

## Where to look

1. The extraction protocol, GEO's `!Sample_extract_protocol_ch1`, or the
   SDRF's protocol description, which names the procedure and often cites it.
2. The paper's Methods, for the assay this sample belongs to.

**Ignore GEO's `library_strategy`.** Submitters choose it from a fixed list
that has no entry for most protocols (no iCLIP or eCLIP among them), so a CLIP
study is routinely filed as `RIP-Seq` or `OTHER`. It is not evidence about the
method.

When a series mixes assays (RNA-Seq beside iCLIP), each sample takes its own
assay's method. A sample whose protocol and Methods point to no one method is
left empty.

## For CLIP

The crosslinking settles one case where the name is missing: 4-thiouridine
with UV at 365 nm is PAR-CLIP, inferred with the protocol text quoted. UV at
254 nm only rules PAR-CLIP out: CLIP, iCLIP, eCLIP and their relatives all use
it, so it names none of them.

## Worked examples

| Study | `library_strategy` | Method, from the protocol |
|---|---|---|
| GSE76475 (Rbfox) | `RIP-Seq` | `iCLIP`: "iCLIP protocol (König J et al, Nat Struct Mol Biol. 2010 …)" |
| GSE215250 (PARP13) | `OTHER` | `eCLIP`: "eCLIP Standard Operating Procedure v1.P 20151108 (van Nostrand et al, Nat. Methods 2016)" |
| GSE113638 (AGO) | `RIP-Seq` | `iCLIP`: König 2011, UV 254 nm |
| GSE78030 (m6A readers) | `OTHER` | `iCLIP`: Huppertz 2014 |
