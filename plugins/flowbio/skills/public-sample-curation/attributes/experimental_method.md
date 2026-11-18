# Experimental Method

**What it means.** The published protocol the library was made with: the CLIP
variant, such as `iCLIP`, `eCLIP`, `seCLIP`, `irCLIP`, `PAR-CLIP`,
`HITS-CLIP`, `iCLAP` or `uvCLAP`.

**How Flow records it.** Free text, as the protocol is usually written.

## Where to look

1. The extraction protocol, GEO's `!Sample_extract_protocol_ch1`, or the
   SDRF's protocol description, which names the procedure and often cites it.
2. The paper's Methods, for the assay this sample belongs to.

**Ignore GEO's `library_strategy`.** Submitters choose it from a fixed list
that has no iCLIP or eCLIP entry, so a CLIP study is routinely filed as
`RIP-Seq` or `OTHER`. That is not evidence about the method.

The crosslinking tells variants apart where the name is missing: UV at 254 nm
is conventional CLIP or iCLIP, while 365 nm with 4-thiouridine is PAR-CLIP.
A method read off the crosslinking is inferred, with the protocol text quoted.

When a series mixes assays (RNA-Seq beside iCLIP), each sample takes its own
assay's method. A sample whose protocol names no method is left empty.

## Worked examples

| Study | `library_strategy` | Method, from the protocol |
|---|---|---|
| GSE76475 (Rbfox) | `RIP-Seq` | `iCLIP`: data processing says "library strategy: iCLIP-seq" |
| GSE113638 (AGO) | `RIP-Seq` | `iCLIP`: König 2011, UV 254 nm |
| GSE78030 (m6A readers) | `OTHER` | `iCLIP`: Huppertz 2014 |
| GSE215250 (PARP13) | | `eCLIP`, from the series title and Methods |
