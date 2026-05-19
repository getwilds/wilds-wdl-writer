version 1.0

import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-star/ww-star.wdl" as star_tasks
import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-deseq2/ww-deseq2.wdl" as deseq2_tasks
import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-rseqc/ww-rseqc.wdl" as rseqc_tasks
import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-bedparse/ww-bedparse.wdl" as bedparse_tasks

struct SampleInfo {
    String name
    File r1
    File r2
    String condition
}

struct RefGenome {
    String name
    File fasta
    File gtf
}

workflow star_deseq2 {
  input {
    Array[SampleInfo] samples
    RefGenome reference_genome
    String reference_level = ""
    String contrast = ""
    Int star_cpu = 8
    Int star_memory_gb = 64
    Int genome_sa_index_nbases = 14
  }

  call star_tasks.build_index { input:
      reference_fasta = reference_genome.fasta,
      reference_gtf = reference_genome.gtf,
      cpu_cores = star_cpu,
      memory_gb = star_memory_gb,
      genome_sa_index_nbases = genome_sa_index_nbases
  }

  # Convert GTF to BED for RSeQC
  call bedparse_tasks.gtf2bed { input:
      gtf_file = reference_genome.gtf
  }

  scatter (sample in samples) {
    String sample_name = sample.name
    String sample_condition = sample.condition

    call star_tasks.align_two_pass { input:
        star_genome_tar = build_index.star_index_tar,
        r1 = sample.r1,
        r2 = sample.r2,
        name = sample.name + "." + reference_genome.name,
        cpu_cores = star_cpu,
        memory_gb = star_memory_gb
    }

    call rseqc_tasks.run_rseqc { input:
        sample_name = sample.name,
        bam_file = align_two_pass.bam,
        bam_index = align_two_pass.bai,
        ref_bed = gtf2bed.bed_file
    }
  }

  call deseq2_tasks.combine_count_matrices { input:
      gene_count_files = align_two_pass.gene_counts,
      sample_names = sample_name,
      sample_conditions = sample_condition
  }

  call deseq2_tasks.run_deseq2 { input:
      counts_matrix = combine_count_matrices.counts_matrix,
      sample_metadata = combine_count_matrices.sample_metadata,
      reference_level = reference_level,
      contrast = contrast
  }

  output {
    Array[File] star_bam = align_two_pass.bam
    Array[File] star_bai = align_two_pass.bai
    Array[File] star_gene_counts = align_two_pass.gene_counts
    Array[File] star_log_final = align_two_pass.log_final
    Array[File] star_log_progress = align_two_pass.log_progress
    Array[File] star_log = align_two_pass.log
    Array[File] star_sj = align_two_pass.sj_out
    Array[File] rseqc_qc_summary = run_rseqc.rseqc_summary
    File combined_counts_matrix = combine_count_matrices.counts_matrix
    File sample_metadata = combine_count_matrices.sample_metadata
    File deseq2_all_results = run_deseq2.deseq2_results
    File deseq2_significant_results = run_deseq2.deseq2_significant
    File deseq2_normalized_counts = run_deseq2.deseq2_normalized_counts
    File deseq2_pca_plot = run_deseq2.deseq2_pca_plot
    File deseq2_volcano_plot = run_deseq2.deseq2_volcano_plot
    File deseq2_heatmap = run_deseq2.deseq2_heatmap
  }
}
