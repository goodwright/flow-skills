---
name: splicing-analysis
description: Use when the user asks about alternative splicing, differential splicing or exon inclusion from RNA-seq — which exons an RNA-binding protein (RBP) or a perturbation regulates, whether a knockdown or knockout changes splicing, or where an RBP binds relative to the exons it regulates (RNA maps). Applies whenever splicing, rMATS, PSI or dPSI, cassette or skipped exons, exon inclusion, splicing regulation or RNA maps come up. Runs rMATS on Flow through the Differential splicing analysis pipeline (rnasplice) from RNA-Seq BAMs, calls regulated exons from JCEC counts at FDR < 0.05 and |dPSI| > 0.1, uses unchanged exons as the background, and draws RNA maps with ulelab/rna_maps from genomic Clippy peaks. Use flow-ai to run pipelines and fetch files, and clip-analysis for the CLIP data.
---

When using RNA-seq to study splicing, always apply the following rules:

Quantify splicing with rMATS on Flow, using the "Differential splicing analysis" pipeline (rnasplice), started from the genome BAMs of the samples' RNA-Seq execution. Follow flow-ai to run it:
- Take each sample's BAM ("*.markdup.sorted.bam") from one RNA-Seq execution; a sample can have BAMs from several executions.
- Take the genome FASTA, GTF and transcripts FASTA from the Prepare RNA-Seq Genome execution that the RNA-Seq execution used (follow its star_index data param to the execution that made it).
- Set strandedness and single_end per sample from that sample's RSeQC "infer_experiment.txt", not from sample metadata, which is often "auto". rMATS needs the real value, and all samples in a comparison must agree.
- Set the read length from STAR's "Log.final.out" ("Average input read length" is summed over both mates for paired-end data).
- List the knockdown, knockout or treated condition as treatment and the control as control in the contrasts file. rMATS then reports dPSI (IncLevelDifference) as treatment minus control.
- Use unpaired statistics unless each treated replicate has its own matched control.

Use the JCEC files ("*.MATS.JCEC.txt"), never the JC files.
A regulated event has FDR < 0.05 and |dPSI| > 0.1. With dPSI as knockdown minus control, an enhanced exon (the RBP promotes inclusion) has dPSI < -0.1 and a silenced exon (the RBP represses inclusion) has dPSI > 0.1.
The background is unchanged exons, never all annotated exons: control exons have |dPSI| < 0.05 and maximum PSI < 0.9, and constitutive exons have |dPSI| < 0.05 and maximum PSI > 0.9. Exons with |dPSI| between 0.05 and 0.1 belong to no group.
To relate RBP binding to splicing, draw RNA maps with ulelab/rna_maps (https://github.com/ulelab/rna_maps) in rMATS mode, on skipped exons ("SE.MATS.JCEC.txt"), with "--maxfdr 0.05 --maxenh -0.1 --minsil 0.1" so its groups match the rules above. Give it the RBP's genomic Clippy peaks ("_Peaks.bed", see clip-analysis) as "-x", and the genome FASTA and index used for the RNA-seq and CLIP data. Follow the instructions in that repository to install and run it.
Report the number of enhanced, silenced, control and constitutive exons for every comparison, and say which comparisons had too few regulated exons to draw a map.
