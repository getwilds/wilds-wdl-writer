version 1.0

import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-sra/ww-sra.wdl" as sra_tasks
import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-star/ww-star.wdl" as star_tasks

struct MYgenome {
    String name
    File fasta
    File gtf
}

workflow sra_star {
  input {
    Array[String] sra_id_list
    MYgenome ref_genome
    Int sjdb_overhang = 100
    Int genome_sa_index_nbases = 14
    Int ncpu = 12
    Int memory_gb = 64
    Int? max_reads
    File? ngc_file
  }

  call star_tasks.build_index { input:
      reference_fasta = ref_genome.fasta,
      reference_gtf = ref_genome.gtf,
      sjdb_overhang = sjdb_overhang,
      genome_sa_index_nbases = genome_sa_index_nbases,
      cpu_cores = ncpu
  }

  scatter ( id in sra_id_list ){
    call sra_tasks.fastqdump { input:
        sra_id = id,
        max_reads = max_reads,
        ngc_file = ngc_file
    }

    # Paired-end alignment
    if (fastqdump.is_paired_end) {
      call star_tasks.align_two_pass as align_paired { input:
          star_genome_tar = build_index.star_index_tar,
          name = id,
          r1 = fastqdump.r1_end,
          r2 = fastqdump.r2_end,
          sjdb_overhang = sjdb_overhang,
          memory_gb = memory_gb,
          cpu_cores = ncpu,
          star_threads = ncpu
      }
    }

    # Single-end alignment
    if (!fastqdump.is_paired_end) {
      call star_tasks.align_two_pass as align_single { input:
          star_genome_tar = build_index.star_index_tar,
          name = id,
          r1 = fastqdump.r1_end,
          sjdb_overhang = sjdb_overhang,
          memory_gb = memory_gb,
          cpu_cores = ncpu,
          star_threads = ncpu
      }
    }

    File bam_out = select_first([align_paired.bam, align_single.bam])
    File bai_out = select_first([align_paired.bai, align_single.bai])
    File gene_counts_out = select_first([align_paired.gene_counts, align_single.gene_counts])
    File log_out = select_first([align_paired.log, align_single.log])
    File sj_out = select_first([align_paired.sj_out, align_single.sj_out])
  }

  output {
    Array[File] star_bam = bam_out
    Array[File] star_bai = bai_out
    Array[File] star_gene_counts = gene_counts_out
    Array[File] star_log = log_out
    Array[File] star_sj = sj_out
  }
}

