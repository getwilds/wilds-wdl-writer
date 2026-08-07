# Example:

## User input

Input data format: fastq
Requested operations: copy_number_variation_detection, sequence_alignment

## Available tasks

run_cnvkit:
  description: Run CNVkit copy number analysis on tumor sample
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-cnvkit/ww-cnvkit.wdl
  operation: copy_number_variation_detection
  input_sample_required:
  - tumor_bam:nucleic_acid_sequence_alignment:bam
  - tumor_bai:data_index:bai
  input_reference_required: reference_cnn:data_index:cnn
  output_sample:
  - cnv_calls:sequence_variations:cns
  - cnv_segments:sequence_variations:cnr
  - cnv_plot:plot:pdf
  output_reference: none
  inputs:
  - sample_name:String
  - tumor_bam:File
  - tumor_bai:File
  - normal_bam:File?
  - normal_bai:File?
  - reference_cnn:File
  - target_bed:File?
  outputs:
  - cnv_segments:File
  - cnv_calls:File
  - cnv_plot:File
bowtie2_align:
  description: Task for aligning sequence reads to a reference genome using Bowtie 2
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-bowtie2/ww-bowtie2.wdl
  operation: sequence_alignment
  input_sample_required: reads:nucleic_acid_sequence:fastq
  input_reference_required: bowtie2_index_tar:data_index:tar_format
  output_sample:
  - sorted_bam:nucleic_acid_sequence_alignment:bam
  - sorted_bai:data_index:bai
  output_reference: none
  inputs:
  - bowtie2_index_tar:File
  - reads:File
  - name:String
  - mates:File?
  outputs:
  - sorted_bam:File
  - sorted_bai:File
bowtie_align:
  description: Task for aligning short reads to a reference genome using Bowtie
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-bowtie/ww-bowtie.wdl
  operation: sequence_alignment
  input_sample_required: reads:nucleic_acid_sequence:fastq
  input_reference_required: bowtie_index_tar:data_index:tar_format
  output_sample:
  - sorted_bam:nucleic_acid_sequence_alignment:bam
  - sorted_bai:data_index:bai
  output_reference: none
  inputs:
  - bowtie_index_tar:File
  - reads:File
  - name:String
  - mates:File?
  outputs:
  - sorted_bam:File
  - sorted_bai:File
bwa_mem:
  description: Task for aligning sequence reads using BWA-MEM
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-bwa/ww-bwa.wdl
  operation: sequence_alignment
  input_sample_required: reads:dna_sequence:fastq
  input_reference_required:
  - bwa_genome_tar:data_index:tar_format
  - reference_fasta:dna_sequence:fasta
  output_sample:
  - sorted_bam:nucleic_acid_sequence_alignment:bam
  - sorted_bai:data_index:bai
  output_reference: none
  inputs:
  - bwa_genome_tar:File
  - reference_fasta:File
  - reads:File
  - name:String
  - mates:File?
  outputs:
  - sorted_bam:File
  - sorted_bai:File

## Output

selected_tasks:
- bwa_mem
- run_cnvkit
