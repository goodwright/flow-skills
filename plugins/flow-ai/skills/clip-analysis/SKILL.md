---
name: clip-analysis
description: Use when the user asks a biological question that CLIP data can answer — where an RNA-binding protein binds across the transcriptome, which genes or regions it binds, what sequence motif it recognizes, or when they want QC'd crosslink data, peaks for downstream analysis, or a signal plot over a gene. Applies whenever CLIP, iCLIP, CLIP-Seq, crosslinking immunoprecipitation, RNA-binding proteins (RBPs), binding sites, binding motifs, crosslinks, or CLIP peaks come up, even if the user names no specific file or pipeline. Restricts analysis to CLIP-Seq v1.7 or v1.6 pipeline outputs and always QCs each dataset first (PCR duplication rate and uniquely-mapped crosslinks from the UMICollapse log; premap tRNA/rRNA enrichment from summary_type_premapadjusted.tsv; motif enrichment from PEKA), reads gene binding from *.summary_gene_premapadjusted.tsv, uses genomic Clippy peaks for downstream work, and plots signal over a gene with Clipplotr. Does NOT generate CLIP data or run the CLIP-Seq pipeline itself — use flow-ai to fetch the pipeline outputs this skill then interprets.
---

When using CLIP data to research a user's question always apply the following rules:

Only use CLIP-Seq v1.7 or v1.6 pipeline outputs.
QC the data for the user and provide a table of included datasets with the following metrics:
a) PCR duplication rate. Calculated from taking the UMICollapse log and calculating the ratio of input to deduplicated reads.
b) Number of uniquely mapped crosslinks, take this also from the UMICollapse log as the number of deduplicated reads.
c) Take the "summary_type_premapadjusted.tsv" and check if a protein is known to bind to certain regions, that they are enriched in the summary. Premapping is to tRNA and rRNA.
d) If the protein is known to bind to a certain motif, check that this is enriched in PEKA output.
If you need to find motif binding information, look at the PEKA output.
If you need to find gene binding information, look for the files ending with ".summary_gene_premapadjusted.tsv" and inspect those.
If you need peaks for downstream analysis use the genomic Clippy peaks.
If making a point, it can be helpful to plot signal over a gene as an example. To do this, use Clipplotr: https://github.com/ulelab/clipplotr . Follow the instructions on that repository to use it correctly.
