# Purification Target

**What it means.** The protein that was purified, by its gene symbol, or the
kind of control library a sample is. Its annotation describes the construct
that was purified: its tag, and any alteration of the protein.

**How Flow records it.** The value is one of the attribute's options: a gene
symbol, or a control target. Look the symbol up among the options; an alias
resolves to the gene symbol Flow holds (`PARP13` → `ZC3HAV1`), shown as
inferred. The annotation is free text, sent as
`{"value": "<target>", "annotation": "<annotation>"}`; leave it out when there
is nothing to annotate.

## Control libraries

A control library takes its own target, never the protein of the pulldown it
controls:

| Library | Target | Annotation |
|---|---|---|
| Size-matched input (eCLIP, seCLIP) | `SMInput` | empty |
| Bead-only or no-antibody control | `noAbCtrl` | empty |
| IgG control | `IgG` | empty |
| The pulldown on cells lacking the target protein | `AbControl` | empty |
| No-crosslink control (UV omitted) | the real protein | `noUV` |
| GFP-only control construct | `GFP` | empty |

- **A no-crosslink control is not a control target.** The same protein was
  purified with the same antibody; only the UV step was left out, so the
  target is the protein and `noUV` is its annotation (`TARDBP` with `noUV`).
- **A size-matched input and an `AbControl` differ in whether an antibody was
  used.** An input has none. An `AbControl` is the same pulldown on cells that
  do not express the tagged protein, so it has the antibody.
- A sample named `INPUT` or `SMInput` whose target is a real protein is the
  most common error. Check every input row.
- If a control target is not among the options and the attribute takes new
  terms, propose it as a new term. Never map it onto a nearby option.

## The annotation

**Grammar: `[<alteration>-]<terminus><tag>`**: the alteration first, then
the tag, joined by a hyphen. `c` is C-terminal and `n` is N-terminal, written
straight before the tag.

| Target and annotation | Meaning |
|---|---|
| `LARP6`, `nMYC` | full-length LARP6, N-terminal myc tag |
| `LARP6`, `dNTR-nMYC` | LARP6 lacking its N-terminal region, N-terminal myc tag |
| `QKI`, `c3xFLAG-HBH` | QKI with a C-terminal 3xFLAG-HBH, one composite tag |
| `TARDBP`, `M337P` | an untagged point mutant |
| `RBM10`, empty | the endogenous protein |

- An unaltered construct has no alteration prefix: `nMYC`, never `FL-nMYC`.
- An alteration alone is valid (`M337P`), but a terminus with no known tag is
  not.
- Known tags: `3xFLAG-HBH`, `FLAG-HA-HIS`, `3xFLAG`, `FLAG`, `GFP`, `V5`,
  `HA`, `MYC`, `HBH`, `HIS`, `TAP`, `SNAP`, `HALO`, `MS2`, `T7`. A tag is
  always written with its terminus: `cV5`, never `V5` or `C-V5`.

**Tag the pulldown, not the cell line.** Only a sample pulled down with the
anti-tag antibody carries the tag. In a study that mixes tagged and endogenous
pulldowns, a sample pulled down with an antibody against the protein itself
has an empty annotation, even if its cells express a tagged construct. An
input has none either.

**Endogenous or tagged:**

- The Methods name an antibody against the protein, and no construct is
  expressed: endogenous, so the annotation is empty.
- GEO's `expression vector:` names the gene and a tag, or the pulldown
  antibody is anti-FLAG, anti-V5, anti-GFP and the like: tagged.
- `expression vector: empty vector` or a tag alone: a control construct, so
  the annotation is empty.

**The terminus**, in this order:

1. The paper states it ("C-terminally V5-tagged"): quoted.
2. The construct's name puts the tag before or after the gene: `myc-LARP6` is
   N-terminal, `LARP6-myc` C-terminal. Sample titles often carry it when the
   Methods do not. Inferred, with the name quoted.
3. Neither: C-terminal. Tagged-protein CLIP screens clone their ORFs without a
   stop codon, which forces a C-terminal fusion. Inferred, with this reason.

## Where to look

1. The Methods sentence that names the pulldown, for the antibody and so
   whether it is endogenous or tagged.
2. GEO sample titles and characteristics (`protein:`, `antibody:`,
   `expression vector:`), for the target per sample and construct names.
3. The SDRF's `Characteristics` and `Factor Value` columns, for ArrayExpress.

## Worked examples

- **GSE215250 (PARP13 eCLIP):** the target is `ZC3HAV1`, PARP13's gene
  symbol. It is endogenous, so all four pulldowns have an empty annotation.
  The four inputs are `SMInput`.
- **GSE290281 (V5 eCLIP):** most proteins were pulled down with anti-V5, so
  `cV5` by the C-terminal default; the Methods state no terminus. RBM10 and
  RBM22 were pulled down with their own antibodies, so their annotation is
  empty, although the study is a V5 screen.
- **GSE297587 (myc-LARP6):** the titles read `mycLARP6`, so `nMYC`, with an
  alteration prefix for each deletion construct (`dNTR-nMYC`). The myc pulldown
  on untransfected cells is `AbControl`.
