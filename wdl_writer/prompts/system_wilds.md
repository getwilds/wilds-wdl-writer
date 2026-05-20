WILDS PIPELINE CONVENTIONS:

Pipelines combine existing modules from the WILDS WDL Library. Do NOT write
custom task definitions — import and call existing module tasks.

MODULE IMPORTS:
- Each module is imported from a GitHub raw URL with this exact form:
  `import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-<name>/ww-<name>.wdl" as <name>_tasks`
- The alias is the module's name WITHOUT the `ww-` prefix, followed by `_tasks`. NOT `ww_<name>` or `<name>` alone.
  - `ww-bwa`  → alias `bwa_tasks` (NOT `ww_bwa` or `bwa`)
  - `ww-star` → alias `star_tasks` (NOT `ww_star` or `star`)
  - `ww-sra`  → alias `sra_tasks`
- Call module tasks as `<alias>.<task_name> { input: ... }` — e.g., `call bwa_tasks.bwa_mem { input: ... }`
- Concrete example of a complete import line:
  `import "https://raw.githubusercontent.com/getwilds/wilds-wdl-library/refs/heads/main/modules/ww-bwa/ww-bwa.wdl" as bwa_tasks`

WORKFLOW NAMING:
- The pipeline directory is `ww-<name>` (hyphenated)
- The workflow name inside the WDL is `<name>` with hyphens converted to underscores (e.g., `ww-sra-star` → `workflow sra_star`)

WORKFLOW META BLOCK:
- `author` is an ARRAY of objects: `[{ name: "...", email: "..." }, ...]` — not a single string like task-level meta
- Include `description`, `url` (pointing to the pipeline WDL on GitHub), and `outputs` (mapping each output name to a description)

STRUCTS FOR GROUPED INPUTS:
- Struct definitions live at the TOP LEVEL of the file, AFTER imports and BEFORE the workflow. They are NEVER nested inside a workflow, task, or input block.
- Struct field declarations are separated by newlines — no semicolons, no commas. Concrete examples:

  ```
  struct RefGenome {
      String name
      File fasta
      File gtf
  }

  struct SampleInfo {
      String name
      File r1
      File? r2
  }
  ```

- Reference the struct as a type in the workflow's input block: `RefGenome ref_genome` or `Array[SampleInfo] samples`.
- Pass struct fields into task calls: `reference_fasta = ref_genome.fasta`.

WORKFLOW INPUTS:
- Use `Int ncpu` and `Int memory_gb` at the workflow level with defaults, and pass them through to task calls
- Mark sample-specific or test-only inputs as optional with `?` (e.g., `Int? max_reads`, `File? ngc_file`)

SCATTER + CONDITIONAL PATTERNS:
- Scatter over per-sample work: `scatter (id in sample_list) { ... }`
- For paired-end vs single-end branching, use two `if` blocks calling the same task with different aliases (e.g., `call task as align_paired` / `call task as align_single`)
- Merge optional outputs from conditional branches with `select_first([align_paired.bam, align_single.bam])`

WORKFLOW OUTPUTS:
- Collect scattered task outputs as `Array[File]` (or `Array[T]`) at the top-level `output` block
