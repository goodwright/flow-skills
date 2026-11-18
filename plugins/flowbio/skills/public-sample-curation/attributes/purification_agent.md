# Purification Agent

**What it means.** The antibody, or other reagent, that purified the protein
in the pulldown.

**How Flow records it.** Free text, in one spelling per reagent:

`<Host> Anti-<TARGET> (<Vendor> <Catalog>)`, for example
`Rabbit Anti-PARP13 (Thermo Fisher PA5-31650)`.

- **Host** is the species the antibody was raised in. Leave it out when
  neither the paper nor the vendor's catalog entry gives it:
  `Anti-PARP13 (Thermo Fisher PA5-31650)`.
- **TARGET** is what the antibody recognises: the protein, or the tag for an
  anti-tag pulldown (`Mouse Anti-V5 (Thermo Fisher R960-25)`).
- A tag pulldown that uses no antibody is `Strep/His affinity tag purification`
  (iCLAP).

## Leave it empty

- On a size-matched input, a bead-only control and an IgG control. No antibody
  purified them. Never copy the pulldown's antibody onto its input.
- When the search below finds no reagent. Say what you searched.

## Where to look

1. **The Methods sentence that names the assay** ("eCLIP was performed … using
   anti-PARP13 antibody (Thermo Fisher, PA5-31650)"). This decides it.
2. The Key Resources or reagents table, only to complete the vendor and
   catalog of the antibody step 1 named.
3. GEO characteristics: `antibody:`, `clip antibody:`.
4. The SDRF's `Factor Value[IMMUNOPRECIPITATE]`. Usually too vague
   ("anti-TIA1 antibody"), so go back to the paper.
5. Supplementary reagent tables, when steps 1 to 4 name nothing. "The Methods
   don't say" is not "the paper doesn't say": a supplement you could not open
   is reported as not read.

The paper usually lists several antibodies for a protein, one for Western
blots and one for the pulldown. **Never take the first antibody listed for
the protein.** Take the one in the sentence that names the pulldown.

## Host species

1. The paper states it ("mouse anti-myc antibody"): quoted.
2. The vendor's catalog entry for the cited catalog number: quoted, with the
   catalog page as the source.
3. Neither: leave the host out.

**Reactivity is not host.** Vendor pages advertise the species an antibody
reacts with more prominently than the one it was raised in. Bethyl `A300-864A`
reacts with human, mouse and rat but is raised in rabbit:
`Rabbit Anti-RBFOX2 (Bethyl A300-864A)`. Never infer the host from what seems
likely.

## An antibody that cannot be bought

Tissue CLIP and older studies often use an antibody shared between labs, so
there is no vendor or catalog number. Write the bare form, `Anti-NOVA`, and
say in the review where it came from ("a gift from Robert B Darnell", from the
Acknowledgements). Never invent a vendor or catalog number to fill the format.

A scraped phrase such as `NOVA antibody`, `V5-antibody` or `DHX9-mAb` names no
reagent. It means the lookup is unfinished, not that the antibody is a gift.

## Worked examples

- **GSE215250 (PARP13):** the Methods say "eCLIP was performed … using
  anti-PARP13 antibody (Thermofisher Scientific, PA5-31650)", and the Key
  Resources table lists it as a rabbit polyclonal, so the four pulldowns are
  `Rabbit Anti-PARP13 (Thermo Fisher PA5-31650)`. The four size-matched inputs
  are empty.
- **E-MTAB-1008 (Nova iCLIP):** the Methods say "an anti-Nova antibody", and
  the Acknowledgements thank Robert B Darnell for sharing it, so `Anti-NOVA`.
