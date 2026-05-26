"""Command-line user interface for collecting WDL pipeline build inputs.

Presents numbered menus for input data type, analysis goal, and optional tool
preferences. No free-form text is accepted (prevents prompt injection, PHI
leakage, and toxic content generation). Outputs a dict of ChromaDB metadata
keywords ready for use as retrieval filters.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Option definitions
# Each entry is a plain dict so callers can read individual fields cleanly.
# EDAM terms match those stored in the ChromaDB `wdl_tasks` collection (see
# ingestion.py and docs/mvp_design_spec.md §6.1).
# ---------------------------------------------------------------------------

DATA_TYPE_OPTIONS: list[dict] = [
    {
        "label": "Paired FASTQ",
        "format_types": ["fastq"],
        "data_types": ["nucleic_acid_sequence"],
    },
    {
        "label": "Single-end FASTQ",
        "format_types": ["fastq"],
        "data_types": ["nucleic_acid_sequence"],
    },
    {
        "label": "BAM / SAM / CRAM (aligned reads)",
        "format_types": ["bam", "sam", "cram"],
        "data_types": ["nucleic_acid_sequence_alignment"],
    },
    {
        "label": "SRA accession IDs",
        "format_types": ["sra"],
        "data_types": ["nucleic_acid_sequence"],
    },
    {
        "label": "VCF (variant calls)",
        "format_types": ["vcf"],
        "data_types": ["sequence_variations"],
    },
    {
        "label": "Count matrix (TSV / CSV)",
        "format_types": ["tsv", "csv"],
        "data_types": ["gene_expression_matrix"],
    },
]

ANALYSIS_GOAL_OPTIONS: list[dict] = [
    {
        "label": "Quality Control (QC)",
        "operations": ["quality_control"],
    },
    {
        "label": "Read Alignment",
        "operations": ["sequence_alignment"],
    },
    {
        "label": "Variant Calling",
        "operations": ["variant_calling"],
    },
    {
        "label": "Differential Expression Analysis",
        "operations": ["differential_gene_expression_analysis"],
    },
    {
        "label": "RNA Quantification",
        "operations": ["rna_seq_quantification"],
    },
    {
        "label": "Download from SRA",
        "operations": ["data_retrieval"],
    },
    {
        "label": "Read Trimming / Filtering",
        "operations": ["sequence_trimming"],
    },
]

# Tool names must match the `tool` metadata field in ChromaDB (set by
# ingestion.py from the WDL filename: `ww-<toolname>.wdl` → `<toolname>`).
TOOL_OPTIONS: list[dict] = [
    {"label": "BWA",        "tool": "bwa"},
    {"label": "STAR",       "tool": "star"},
    {"label": "HISAT2",     "tool": "hisat2"},
    {"label": "GATK",       "tool": "gatk"},
    {"label": "Strelka2",   "tool": "strelka"},
    {"label": "SAMtools",   "tool": "samtools"},
    {"label": "Picard",     "tool": "picard"},
    {"label": "FastQC",     "tool": "fastqc"},
    {"label": "Trimmomatic","tool": "trimmomatic"},
    {"label": "DESeq2",     "tool": "deseq2"},
    {"label": "SRA Tools",  "tool": "sra"},
]


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------


def _print_menu(title: str, options: list[dict], optional: bool = False) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for i, opt in enumerate(options, start=1):
        print(f"  {i:2}. {opt['label']}")
    if optional:
        print(f"   0. Skip (none)")


def _parse_numbers(raw: str, max_n: int, allow_zero: bool = False) -> list[int] | None:
    """Parse a comma-separated string of 1-based menu numbers into 0-based indices.

    Returns None on any invalid input; returns [] when user enters 0 (skip).
    """
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    indices: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        n = int(part)
        if allow_zero and n == 0:
            return []
        if n < 1 or n > max_n:
            return None
        idx = n - 1
        if idx not in indices:
            indices.append(idx)
    return indices


def _prompt_menu(
    title: str,
    options: list[dict],
    multi: bool = True,
    optional: bool = False,
) -> list[int]:
    """Display a menu and loop until valid selections are entered.

    Returns a list of 0-based indices into `options`.
    Returns [] when the menu is optional and the user skips.
    """
    suffix = " (or 0 to skip)" if optional else ""
    prompt_text = "Enter number(s), comma-separated" if multi else "Enter number"
    prompt_text += suffix

    while True:
        _print_menu(title, options, optional=optional)
        try:
            raw = input(f"\n{prompt_text}: ").strip()
        except EOFError:
            raise SystemExit("Input stream closed — exiting.")

        result = _parse_numbers(raw, len(options), allow_zero=optional)
        if result is None:
            print("  Invalid input. Please enter valid number(s) from the menu above.")
            continue
        if not result and not optional:
            print("  At least one selection is required.")
            continue
        return result


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------


def select_data_types() -> list[int]:
    """Prompt user to select one or more input data types.

    Returns 0-based indices into DATA_TYPE_OPTIONS.
    """
    return _prompt_menu(
        "1. What input data do you have?",
        DATA_TYPE_OPTIONS,
        multi=True,
        optional=False,
    )


def select_analysis_goals() -> list[int]:
    """Prompt user to select one or more analysis goals.

    Returns 0-based indices into ANALYSIS_GOAL_OPTIONS.
    """
    return _prompt_menu(
        "2. What are your analysis goals?",
        ANALYSIS_GOAL_OPTIONS,
        multi=True,
        optional=False,
    )


def select_tools() -> list[int]:
    """Prompt user to optionally select preferred bioinformatics tools.

    Returns 0-based indices into TOOL_OPTIONS, or [] if skipped.
    """
    return _prompt_menu(
        "3. Any preferred tools? (optional)",
        TOOL_OPTIONS,
        multi=True,
        optional=True,
    )


# ---------------------------------------------------------------------------
# Keyword parsing
# ---------------------------------------------------------------------------


def parse_to_metadata_keywords(
    data_indices: list[int],
    goal_indices: list[int],
    tool_indices: list[int],
) -> dict:
    """Map user selections to ChromaDB metadata keyword sets.

    Returns:
        A dict with keys matching the `wdl_tasks` ChromaDB metadata fields:
          - input_sample_format_types  list[str]  EDAM format terms
          - input_sample_data_types    list[str]  EDAM data type terms
          - operation                  list[str]  EDAM operation terms
          - tool                       list[str]  tool names as stored in ChromaDB
        Plus human-readable labels for downstream template rendering:
          - data_type_labels           list[str]
          - goal_labels                list[str]
          - tool_labels                list[str]
    """
    format_types: list[str] = []
    data_types: list[str] = []
    for i in data_indices:
        for fmt in DATA_TYPE_OPTIONS[i]["format_types"]:
            if fmt not in format_types:
                format_types.append(fmt)
        for dtype in DATA_TYPE_OPTIONS[i]["data_types"]:
            if dtype not in data_types:
                data_types.append(dtype)

    operations: list[str] = []
    for i in goal_indices:
        for op in ANALYSIS_GOAL_OPTIONS[i]["operations"]:
            if op not in operations:
                operations.append(op)

    tools: list[str] = []
    for i in tool_indices:
        tool = TOOL_OPTIONS[i]["tool"]
        if tool not in tools:
            tools.append(tool)

    return {
        "input_sample_format_types": format_types,
        "input_sample_data_types": data_types,
        "operation": operations,
        "tool": tools,
        "data_type_labels": [DATA_TYPE_OPTIONS[i]["label"] for i in data_indices],
        "goal_labels": [ANALYSIS_GOAL_OPTIONS[i]["label"] for i in goal_indices],
        "tool_labels": [TOOL_OPTIONS[i]["label"] for i in tool_indices],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_selections(keywords: dict) -> list[str]:
    """Return warning messages for incompatible keyword combinations.

    An empty list means no compatibility issues were detected.
    Expects `keywords` as returned by parse_to_metadata_keywords().
    """
    fmts = set(keywords["input_sample_format_types"])
    dtypes = set(keywords["input_sample_data_types"])
    ops = set(keywords["operation"])
    tools = set(keywords["tool"])

    warnings: list[str] = []

    if "sra" in fmts and "data_retrieval" not in ops:
        warnings.append(
            "SRA accession IDs selected as input but 'Download from SRA' is "
            "not among your analysis goals."
        )
    if "gene_expression_matrix" in dtypes and "variant_calling" in ops:
        warnings.append("Count matrix input is not compatible with Variant Calling.")
    if "differential_gene_expression_analysis" in ops and not (
        {"nucleic_acid_sequence", "gene_expression_matrix"} & dtypes
    ):
        warnings.append(
            "Differential Expression Analysis expects FASTQ reads or a count "
            "matrix as input."
        )
    if (
        "nucleic_acid_sequence_alignment" in dtypes
        and "sequence_alignment" in ops
        and not ({"fastq", "sra"} & fmts)
    ):
        warnings.append(
            "Read Alignment is selected but your input is already aligned "
            "(BAM / SAM / CRAM). Did you mean Variant Calling?"
        )
    if "star" in tools and "variant_calling" in ops:
        warnings.append(
            "STAR is an RNA-seq aligner; pairing it with Variant Calling is "
            "unusual. Consider BWA or HISAT2 for DNA, or add RNA Quantification "
            "as a goal."
        )
    if "bwa" in tools and "differential_gene_expression_analysis" in ops:
        warnings.append(
            "BWA is a DNA aligner; Differential Expression Analysis typically "
            "uses an RNA-seq aligner (STAR or HISAT2)."
        )
    if "deseq2" in tools and "differential_gene_expression_analysis" not in ops:
        warnings.append(
            "DESeq2 is selected as a tool but Differential Expression Analysis "
            "is not among your goals."
        )
    if "gatk" in tools and "variant_calling" not in ops:
        warnings.append(
            "GATK is selected as a tool but Variant Calling is not among your goals."
        )

    return warnings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def collect_user_input() -> dict:
    """Run the full CLI input flow and return ChromaDB metadata keywords.

    Guides the user through data type, analysis goal, and tool menus, warns
    on incompatible combinations, and asks for confirmation before returning.

    Returns:
        A dict as produced by parse_to_metadata_keywords() — ChromaDB-ready
        metadata keyword sets plus human-readable labels.
    """
    print("\n=== WILDS WDL Writer ===")
    print("Select from the numbered menus below. No free-text input is accepted.")

    while True:
        data_indices = select_data_types()
        goal_indices = select_analysis_goals()
        tool_indices = select_tools()

        keywords = parse_to_metadata_keywords(data_indices, goal_indices, tool_indices)
        warnings = validate_selections(keywords)

        if warnings:
            print("\n[!] Compatibility warnings:")
            for w in warnings:
                print(f"  - {w}")
            print()
            try:
                answer = input(
                    "Press Enter to re-select, or type 'continue' to proceed anyway: "
                ).strip().lower()
            except EOFError:
                raise SystemExit("Input stream closed — exiting.")
            if answer != "continue":
                continue

        print("\n--- Your selections ---")
        print(f"  Input data:  {', '.join(keywords['data_type_labels'])}")
        print(f"  Goals:       {', '.join(keywords['goal_labels'])}")
        print(f"  Tools:       {', '.join(keywords['tool_labels']) or '(none specified)'}")

        try:
            answer = input("\nConfirm? [y/n]: ").strip().lower()
        except EOFError:
            raise SystemExit("Input stream closed — exiting.")
        if answer == "y":
            return keywords
        print("\nStarting over...\n")


if __name__ == "__main__":
    result = collect_user_input()
    print("\nChromaDB metadata keywords:")
    for k, v in result.items():
        print(f"  {k}: {v}")
