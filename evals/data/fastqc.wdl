version 1.0

import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-fastqc/ww-fastqc.wdl" as fastqc_tasks

struct SampleInfo {
    String name
    File r1
    File? r2
}

workflow fastqc_only {

  input {
    Array[SampleInfo] samples
    Int ncpu = 2
    Int memory_gb = 4
  }

  scatter (sample in samples) {
    call fastqc_tasks.run_fastqc {
      input:
        r1_fastq = sample.r1,
        r2_fastq = sample.r2,
        cpu_cores = ncpu,
        memory_gb = memory_gb,
    }
  }

  output {
    Array[Array[File]] html_reports = run_fastqc.html_reports
    Array[Array[File]] zip_reports = run_fastqc.zip_reports
  }
}
