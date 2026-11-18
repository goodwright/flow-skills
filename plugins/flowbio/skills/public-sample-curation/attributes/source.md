# Source

**What it means.** The cell line, cell type or tissue the sample came from.

**How Flow records it.** One of the attribute's options: the general line or
tissue (`HeLa`, `HEK293T`, `liver`). The annotation carries detail beyond it,
most often a named sub-line, clone or derivation, and is sent as
`{"value": "HeLa", "annotation": "Kyoto"}`.

| Source | Annotation | When |
|---|---|---|
| `HeLa` | `Kyoto` | the study uses a named sub-line |
| `HEK293T` | empty | the plain parental line |
| `HeLa` | `Flp-In T-REx` | an engineered derivative |

Leave the annotation empty unless the paper names a specific lineage or
clone. Never restate the line in it, and never put a genotype or treatment
there.

## Where to look

1. **The paper's cell line**, from its Methods or Key Resources table (often
   with an ATCC id or RRID: `HEK 293T — ATCC CRL-3216` is `HEK293T`).
2. GEO's `cell line:` or `cell type:` characteristic, or the SDRF's
   `Characteristics[CellLine]`.
3. GEO's `!Sample_source_name_ch1`, only when nothing above states it. It is
   often a supplier phrase or a loose description.

For tissue, the same order applies with `tissue:` in place of `cell line:`.

## Never a source

- A supplier phrase: `ATCC Cell Lines` (GSE105082's source name; the line is
  `HeLa`).
- A generic description: `human embryonic kidney` (GSE215250's source name).
- A placeholder: `cell line`, `tissue`, `N/A`, `unknown`.

When only such a phrase is found, leave the source empty and say so.

## Lines that are easy to confuse

**HEK293 and HEK293T** are different lines: HEK293T is the derivative carrying
SV40 large T. GEO often says one where the paper says the other. When the
sources disagree, or only GEO names the line, show what each says and flag
the value: the user always confirms which it is.

## Worked examples

- **GSE215250:** GEO says `cell line: HEK293`, and its source name is
  `human embryonic kidney`, but the paper's Methods use HEK293T throughout.
  Show both quotes, propose `HEK293T` from the paper, and flag it.
- **GSE105082:** the source name is `ATCC Cell Lines`, which is no source; the
  line is `HeLa`, from the paper.
- **GSE255777:** human liver explants: `tissue: liver`, so the source is
  `liver`, quoted from GEO.
