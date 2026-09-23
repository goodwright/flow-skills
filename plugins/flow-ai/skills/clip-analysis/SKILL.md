---
name: clip-analysis
description: Use when the user asks a biological question CLIP data can answer — where an RNA-binding protein binds, which genes or regions it binds, what motif it recognizes, or when they want QC'd crosslink data, peaks for downstream analysis, or a signal plot over a gene. Applies whenever CLIP, iCLIP, CLIP-Seq, crosslinking immunoprecipitation, RNA-binding proteins (RBPs), binding sites, binding motifs, crosslinks, or CLIP peaks come up, even if no specific file or pipeline is named. Restricts analysis to CLIP-Seq v1.7 or v1.6 outputs and always QCs each dataset first (PCR duplication and uniquely-mapped crosslinks from the UMICollapse log; premap tRNA/rRNA enrichment from summary_type_premapadjusted.tsv; motif enrichment from PEKA), measures gene and region binding from genomic Clippy peaks annotated with the run's regions GTF, and plots signal over a gene with Clipplotr. Does NOT generate CLIP data or run the pipeline itself — use flow-ai to fetch the outputs this skill interprets.
---

When using CLIP data to research a user's question always apply the following rules:

Only use CLIP-Seq v1.7 or v1.6 pipeline outputs.
Work from small files to large ones, narrowing at each step, so you never fetch outputs you won't use:
1. From sample metadata alone, drop controls (size-matched inputs, IgG, no-antibody, tag-only) and samples outside the question.
2. QC the rest from the small files only: the "unique_genome.dedup_UMICollapse.log" and "summary_type_premapadjusted.tsv" (a few KB each).
3. Decide which datasets and RBPs you will analyse, and tell the user how many and why.
4. Only then fetch the Clippy peaks (~10 MB each) and PEKA outputs, for those datasets only. Reduce each file to what you need as it arrives and delete it, rather than keeping every file.
QC the data for the user and provide a table of included datasets with the following metrics:
a) PCR duplication rate. Calculated from taking the UMICollapse log and calculating the ratio of input to deduplicated reads.
b) Number of uniquely mapped crosslinks, take this also from the UMICollapse log as the number of deduplicated reads.
c) Take the "summary_type_premapadjusted.tsv" and check if a protein is known to bind to certain regions, that they are enriched in the summary. Premapping is to tRNA and rRNA.
d) If the protein is known to bind to a certain motif, check that this is enriched in PEKA output.
If you need to find motif binding information, look at the PEKA output.
To find which samples have v1.6 or v1.7 outputs, follow Example 18 in the flow-ai skill's examples.md.
If you need gene binding information, use the genomic Clippy peaks: the "_Peaks.bed" files from the CLIPPY_GENOME step (not Paraclu, not the transcript-level Clippy peaks). Assign each peak to a gene and region (5'UTR, CDS, intron, 3'UTR, ncRNA), on the same strand, using the regions GTF from the same pipeline run: the execution's data_params.regions_resolved_gtf, which assigns each nucleotide to a single annotation. Report binding per region, not per whole gene.
If a run's regions GTF has been deleted (404) or is missing, use the regions_resolved_gtf of another run with the same data_params.gtf id. Before using it, check that the "Length" column of the two runs' "summary_type_premapadjusted.tsv" files is identical: those lengths come from the regions GTF, so identical lengths mean the same segmentation. Tell the user which runs you substituted it for.
Do not use the ".summary_gene_premapadjusted.tsv" files to rank genes, compare RBPs or test gene sets. They are whole-gene crosslink counts, dominated by intronic signal in long genes.
If you need peaks for downstream analysis use the genomic Clippy peaks.
If making a point, it can be helpful to plot signal over a gene as an example. To do this, use Clipplotr: https://github.com/ulelab/clipplotr . Follow the instructions on that repository to use it correctly.
