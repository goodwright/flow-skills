# Purification Target

**What it means.** The protein a pulldown purified, by its gene symbol, or the
kind of control library a sample is. Its annotation describes the construct
that was purified: its tag, and any alteration of the protein.

**How Flow records it.** A gene symbol or a control target, matched to the
attribute's options, and an annotation in the grammar below.

**Decide from the pulldown, not from the cells.** What a sample's target and
annotation are depends on what its antibody pulled down. Cells can express a
tagged construct that a given pulldown never touches.

## CLIP control libraries

A control library takes its own target, never the protein of the pulldown it
controls. The table covers CLIP; a ChIP-Seq input has no row here yet.

| Library | Target | Annotation |
|---|---|---|
| Size-matched input (eCLIP, seCLIP, iCLIP) | `SMInput` | empty |
| Bead-only or no-antibody control | `noAbCtrl` | empty |
| IgG control | `IgG` | empty |
| The pulldown run on cells lacking the target protein | `AbControl` | empty |
| No-crosslink control (UV omitted) | the real protein | `noUV` |
| Anti-GFP pulldown of cells expressing GFP alone | `GFP` | empty |

- **A no-crosslink control is not a control target.** The same protein was
  purified with the same antibody; only the UV step was left out, so the
  target is the protein and `noUV` its annotation (`TARDBP` with `noUV`).
- **A size-matched input and an `AbControl` differ in whether an antibody was
  used.** An input has none. An `AbControl` is the same pulldown on cells that
  do not express the tagged protein, so it has the antibody.
- A sample named `INPUT` or `SMInput` whose target is a real protein is the
  most common error. Check every input row.
- A pulldown of something other than a protein, such as anti-m6A in m6A
  iCLIP, has no protein target: leave the target empty and say what was
  pulled down.

## The annotation

An annotation is one of:

- `<terminus><tag>`: a tagged, unaltered protein (`nMYC`, `cV5`);
- `<alteration>-<terminus><tag>`: a tagged, altered protein (`dNTR-nMYC`);
- `<alteration>`: an untagged, altered protein (`M337P`);
- `noUV`: a no-crosslink control (see above);
- empty: the endogenous protein, or a control target.

The terminus is `c` for C-terminal or `n` for N-terminal, written straight
before the tag.

| Target and annotation | Meaning |
|---|---|
| `LARP6`, `nMYC` | full-length LARP6, N-terminal myc tag |
| `LARP6`, `dNTR-nMYC` | LARP6 lacking its N-terminal region, N-terminal myc tag |
| `QKI`, `c3xFLAG-HBH` | QKI with a C-terminal 3xFLAG-HBH, one composite tag |
| `TARDBP`, `M337P` | an untagged point mutant |
| `RBM22`, empty | the endogenous protein |

- An unaltered construct has no alteration: `nMYC`, never `FL-nMYC`.
- A tag is always written with its terminus: `cV5`, never `V5` or `C-V5`.
- Tags in common use: `3xFLAG-HBH`, `FLAG-HA-HIS`, `3xFLAG`, `FLAG`, `GFP`,
  `V5`, `HA`, `MYC`, `HBH`, `HIS`, `TAP`, `SNAP`, `HALO`, `MS2`, `T7`. A tag
  not among them, such as a Strep/His tag, is written the same way under the
  name the paper uses and flagged for the user to confirm.
- No convention combines `noUV` with a tag. For a no-crosslink control of a
  tagged protein, propose the tag and flag that the sample is a no-UV control.

**Tagged or endogenous, by the pulldown's antibody:**

- The antibody is against a tag (anti-FLAG, anti-V5, anti-GFP, anti-myc and
  the like): the purified protein is tagged. Take the tag and its terminus
  from the construct (GEO's `expression vector:` or `genotype:`, the paper).
- The antibody is against the protein itself: endogenous, so the annotation
  is empty, even when the same cells express a tagged construct.
- A pulldown of a control construct (an empty vector, a tag alone) is a
  control: see the table above.

**The terminus**, in this order:

1. The paper states it ("C-terminally V5-tagged"): quoted.
2. The construct's name puts the tag before or after the gene: `myc-LARP6` is
   N-terminal, `LARP6-myc` C-terminal. Sample titles often carry it when the
   Methods do not. Inferred, with the name quoted.
3. Neither, in a tagged-protein CLIP screen: C-terminal. Such screens clone
   their ORFs without a stop codon, which forces a C-terminal fusion.
   Inferred, with this reason.

## Where to look

1. The Methods sentence that names the pulldown, for its antibody.
2. GEO sample titles and characteristics (`clip antibody:`, `antibody:`,
   `expression vector:`, `genotype:`), for each sample's antibody and
   construct.
3. The SDRF's `Characteristics` and `Factor Value` columns, for ArrayExpress.

## Worked examples

- **GSE215250 (PARP13 eCLIP):** the target is `ZC3HAV1`, PARP13's gene
  symbol. The pulldowns are endogenous, so all four have an empty annotation.
  The four inputs are `SMInput`.
- **GSE228608 (ZBTB48 and FTO iCLIP):** the FTO samples were pulled down with
  anti-FLAG from cells carrying `pcDNA5/FRT/TO-FLAG` FTO (the paper's
  FLAG-FTO), so `nFLAG` from the construct's name. The ZBTB48 samples were
  pulled down with an antibody against ZBTB48 from wild-type cells, so their
  annotation is empty. The m6A iCLIP samples were pulled down with anti-m6A,
  so they have no protein target, although their cells express FTO, ZBTB48
  or GFP.
- **GSE297587 (myc-LARP6):** the titles read `mycLARP6`, so `nMYC`, with an
  alteration for each deletion construct (`dNTR-nMYC`). The myc pulldown on
  untransfected cells is `AbControl`.
