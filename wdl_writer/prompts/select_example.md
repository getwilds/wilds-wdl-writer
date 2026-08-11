# Example:

## User input

Input data format: fastq
Requested operations: sequence_alignment, variant_calling, annotation

## Available tasks

haplotype_caller:
  description: Call germline SNPs and indels from a BAM file using GATK HaplotypeCaller
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-gatk/ww-gatk.wdl
  operation: variant_calling
  input_sample_required:
  - bam:nucleic_acid_sequence_alignment:bam
  - bam_index:data_index:bai
  input_reference_required:
  - reference_fasta:nucleic_acid_sequence:fasta
  - reference_fasta_index:data_index:fai
  - reference_dict:data_index:dict
  output_sample:
  - vcf:sequence_variations:vcf
  - vcf_index:data_index:tbi
  output_reference: none
  inputs:
  - bam:File
  - bam_index:File
  - reference_fasta:File
  - reference_fasta_index:File
  - reference_dict:File
  outputs:
  - vcf:File
  - vcf_index:File
mutect2:
  description: Call somatic variants using GATK Mutect2 in tumor-only mode with filtering
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-gatk/ww-gatk.wdl
  operation: variant_calling
  input_sample_required:
  - bam:nucleic_acid_sequence_alignment:bam
  - bam_index:data_index:bai
  input_reference_required:
  - gnomad_vcf:sequence_variations:vcf
  - reference_fasta:nucleic_acid_sequence:fasta
  - reference_fasta_index:data_index:fai
  - reference_dict:data_index:dict
  output_sample:
  - vcf:sequence_variations:vcf
  - vcf_index:data_index:tbi
  - unfiltered_vcf:sequence_variations:vcf
  - unfiltered_vcf_index:data_index:tbi
  - stats_file:report:vcf
  - f1r2_counts:report:tar_format
  output_reference: none
  inputs:
  - bam:File
  - bam_index:File
  - reference_fasta:File
  - reference_fasta_index:File
  - reference_dict:File
  - gnomad_vcf:File
  outputs:
  - vcf:File
  - vcf_index:File
  - unfiltered_vcf:File
  - unfiltered_vcf_index:File
  - stats_file:File
  - f1r2_counts:File
annovar_annotate:
  description: Annotate a VCF's variants with ANNOVAR
  url: https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-annovar/ww-annovar.wdl
  operation: annotation
  input_sample_required: vcf_to_annotate:sequence_variations:vcf
  input_reference_required: none
  output_sample:
  - annotated_vcf:sequence_variations:vcf
  - annotated_table:sequence_features:tsv
  output_reference: none
  inputs:
  - vcf_to_annotate:File
  outputs:
  - annotated_vcf:File
  - annotated_table:File
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
- haplotype_caller
- annovar_annotate
