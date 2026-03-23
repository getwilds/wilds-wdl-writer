# MVP Design Spec: WILDS WDL Writer

**Author:** Emma Bishop

**Last modified:** 2026-03-23

**Status:** Draft

**Version:** 1.0

**Reviewers:** None yet

## Table of Contents

1. [Overview](#1-overview)
   - [1.1 Purpose and Problem Statement](#11-purpose-and-problem-statement)
   - [1.2 Users](#12-users)
   - [1.3 Scope](#13-scope)
2. [Success Criteria](#2-success-criteria)
3. [User Stories](#3-user-stories)
4. [User Flow](#4-user-flow)
5. [Data Flow](#5-data-flow)
6. [System Architecture](#6-system-architecture)
   - [6.1 Components](#61-components)
   - [6.2 Technology Stack](#62-technology-stack)
7. [ChromaDB Vector Database](#7-chromadb-vector-database)
   - [7.1 Purpose](#71-purpose)
   - [7.2 Document Structure](#72-document-structure-draft)
   - [7.3 Corpus Curation](#73-corpus-curation)
   - [7.4 Embedding Strategy](#74-embedding-strategy)
8. [LLM Integration](#8-llm-integration)
   - [8.1 Model Selection](#81-model-selection)
   - [8.2 Inference Configuration](#82-inference-configuration)
   - [8.3 Prompt Strategy](#83-prompt-strategy)
   - [8.4 LLM Hosting](#84-llm-hosting)
9. [WDL Validation](#9-wdl-validation)
10. [Tool Selection Module](#10-tool-selection-module)
    - [10.1 Purpose](#101-purpose)
    - [10.2 Approach](#102-approach-draft)
    - [10.3 Output Format](#103-output-format)
    - [10.4 User Interaction](#104-user-interaction-cli)
    - [10.5 Integration with WDL Generation](#105-integration-with-wdl-generation)
11. [Security & Privacy](#11-security--privacy)
12. [Key Design Decisions](#12-key-design-decisions)
    - [12.1 Why Human-in-the-Loop?](#121-why-human-in-the-loop)
    - [12.2 Why RAG Instead of Fine-Tuning?](#122-why-rag-instead-of-fine-tuning)
    - [12.3 Why a Local LLM?](#123-why-a-local-llm)
    - [12.4 Why No Session History?](#124-why-no-session-history)
    - [12.5 Why `all-MiniLM-L6-v2` for Embeddings?](#125-why-all-minilm-l6-v2-for-embeddings)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Deliverables](#14-deliverables)
15. [Future Work (Phase 2+)](#15-future-work-phase-2)

---

## 1. Overview

### 1.1 Purpose and Problem Statement

**Purpose**

WILDS WDL Writer is a local, LLM-based command-line tool for generating complete WDL (Workflow Description Language) workflows using components from the [WILDS WDL Library](https://github.com/getwilds/wilds-wdl-library). Users provide information about their input data and analysis goals via an interactive CLI session. The tool uses RAG (Retrieval-Augmented Generation) to search through curated WDL examples and identify appropriate componenents, which provide context to the language model. The tool incorporates human-in-the-loop approval when selecting bioinformatics tools and when reviewing the final WDL output.

**Problem Statement**

WDL workflows take a long time to write and require significant bioinformatics knowledge. These problems are experienced by both new and experienced WDL users and are a barrier to WDL adoption by labs.

### 1.2 Users

**Target Users**

- **Primary:** Bioinformaticians
- **Secondary:** Postdocs and grad students

**User Needs**

- Able to write WDLs for their use cases
- Faster and/or easier than iterating with an AI chatbot (e.g., ChatGPT, Claude)

### 1.3 Scope

**In Scope:**

- Interactive CLI for collecting user inputs
- RAG retrieval over curated WILDS WDL Library examples
- Human-in-the-loop tool bioinformatics approval checkpoint
- WDL generation using a local LLM
- WDL validation with automatic retry (`miniwdl check`, `sprocket lint`)
- Human-in-the-loop final review and save to disk

**Out of Scope:**

- Web or graphical user interface
- Cloud or cluster execution
- Workflow execution (users run WDLs themselves)
- History or storage of past sessions

## 2. Success Criteria

| Metric | Target |
|---|---|
| Syntax correctness | 100% of generated WDLs pass `miniwdl` and `sprocket` validation |
| Functional correctness | 95% (19/20) of generated WDLs use appropriate tools and parameters |
| Latency: tool plan to user | <15 seconds |
| Latency: full WDL generation | <1 hour |
| Consistency (same inputs → same output) | ≥80% identical; non-identical outputs ≥85% lexical similarity ([`SequenceMatcher`](https://tedboy.github.io/python_stdlib/generated/generated/difflib.SequenceMatcher.html)) and ≥90% pairwise cosine similarity ([`sentence-transformers`](https://sbert.net/docs/quickstart.html)) |


## 3. User Stories

- **US-1: Faster Than Manual Writing** — As a grad student creating a variant calling workflow, I want to generate a complete WDL in under an hour so that I can be more productive than writing it manually or iterating with ChatGPT.
- **US-2: Tool Selection Control** — As a researcher with tool preferences, I want to review and approve which bioinformatics tools are used so that I can ensure the workflow uses tools I'm familiar with or that my lab prefers.
- **US-2: Privacy Requirements** — As a researcher developing unpublished pipelines, I want to generate workflows without sending any information outside Fred Hutch so that I can use it with unpublished or sensitive pipeline designs.
- **US-4: Handling Failures** — As a user whose WDL generation failed validation, I want to receive the best attempt with clear error messages so that I can either regenerate or manually fix the issues.

## 4. User Flow

1. User runs the script and is prompted to select from pre-written values for:
   - Input data types
   - Analysis goals
   - Optional: Preferred tools (exact list TBD)
2. System retrieves relevant WDL examples and extracts tool recommendations
3. System displays a tool selection plan:
   - List of recommended tools (e.g., "BWA-MEM for alignment") with documentation links
   - User approves or rejects each tool; rejected tools show alternatives from the WILDS WDL Library (or "no alternatives" if none exist)
4. User approves tools; system generates WDL
   - Progress messages printed to terminal during generation
   - Validation with automatic retry (up to 10 attempts — exact number TBD after testing)
5. WDL displayed in terminal with one of:
   - **Validation passed:** user prompted to approve or reject
     - **Approve:** WDL saved to disk at a user-specified path
     - **Reject:** User provides a reason; system retries generation once with that context appended
   - **Validation failed after all retries:** best attempt displayed with error messages; user can save it or exit
6. Information on how to get help from OCDO (Data House Calls, etc.) printed at the end


## 5. Data Flow

**Step 1: Input Collection**

- Prompt user for required and optional fields
- Validate that required fields are present and that inputs are mutually compatible
- If validation fails, surface a clear error; otherwise proceed

**Step 2: RAG Retrieval**

- Convert user input to a query string
- Query the `wdl_tasks` ChromaDB collection using metadata filters (analysis category, input/output types); fall back to vector search if metadata filtering yields insufficient results
- For each retrieved task, extract command-line invocations from the command block and query the `tool_docs` collection via vector search to retrieve relevant tool documentation
- Retrieved context includes enriched task chunks and matching tool documentation

**Step 3: Tool Selection**

- Parse retrieved examples to identify candidate tools
- Validate that all candidate tools are present in the WILDS WDL Library
- Present tool list to user with documentation links and alternatives
- Wait for user approval/modifications

**Step 4: Prompt Construction**

Combine into a single LLM prompt:
- System prompt (WDL generation instructions)
- Retrieved WDL examples (RAG context)
- User specifications
- Approved tool list

**Step 5: WDL Generation**

- Send prompt to local LLM; display a progress message

**Step 6: Validation & Retry**

1. Confirm that user-approved tools (and only those tools) appear in the WDL
   - If invalid: send back to LLM with a correction prompt
2. Run `miniwdl check --strict` and `sprocket lint`
   - If valid: proceed to Step 7
   - If invalid: send validation errors back to LLM with a retry prompt; repeat up to 10 times
   - If all retries fail: return best attempt with errors attached

**Step 7: Final Review**

- Display WDL in terminal (in a way user can easily copy/paste)
- Prompt user to approve or reject
  - **Approve:** save to disk at user specified location
  - **Reject:** collect reason; retry generation once with that feedback appended to the prompt

**Latency Budget:**

| Stage | Target |
|---|---|
| Input collection | Interactive (user-paced) |
| RAG retrieval | <5 seconds |
| Tool selection presentation | <15 seconds |
| WDL generation | <1 hour |
| Validation | <3 minutes |
| **Total (no human review time)** | **<1 hour** |


## 6. System Architecture

### 6.1 Components

| Component | Description |
|---|---|
| **CLI entrypoint** | `generate_wdl.py`; drives the full pipeline and handles user I/O |
| **Input collector** | Prompts the user for data types, analysis goals, and optional constraints |
| **RAG retriever** | Queries ChromaDB for the top-k most similar WDL examples using LlamaIndex |
| **ChromaDB store** | Two local ChromaDB collections: `wdl_tasks` (enriched task chunks, metadata-filtered) and `tool_docs` (chunked tool documentation, vector-searched) |
| **Tool selection module** | Extracts, ranks, and presents candidate bioinformatics tools for user approval |
| **LLM client** | Local LLM (via Ollama) that generates WDL given retrieved context and user intent |
| **Approval checkpoints** | Interactive CLI prompts at tool selection and final WDL review |
| **WDL validator** | Runs `miniwdl check --strict` and `sprocket lint`; feeds errors back to LLM on failure |
| **File writer** | Saves the approved WDL to a user-specified output path |

### 6.2 Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| RAG framework | [LlamaIndex](https://www.llamaindex.ai/) | `VectorStoreIndex`, `PromptTemplate`, `CustomQueryEngine`, `Ollama` integration |
| Vector database | [ChromaDB](https://www.trychroma.com/) | Local, no server required |
| Embeddings | [`sentence-transformers`](https://sbert.net/) | `all-MiniLM-L6-v2` or similar |
| LLM runtime | [Ollama](https://ollama.com/) | Runs models locally; no external API calls |
| LLM model | TBD — see Section 8 | Evaluated on WDL generation quality and speed |
| WDL validation | `miniwdl`, `sprocket` | Could possibly just use sprocket |
| CLI | `click` | Can display options for user to enter |

---

## 7. ChromaDB Vector Database

### 7.1 Purpose

Two ChromaDB collections support the RAG pipeline:

- **`wdl_tasks`** — stores enriched WDL task chunks from the WILDS WDL Library. The primary retrieval mechanism is metadata filtering (analysis category, input/output types); vector search is available as a fallback when metadata filters return insufficient results.
- **`tool_docs`** — stores chunked tool documentation. Queried via vector search using command-line invocations extracted from a retrieved task's command block.

### 7.2 Document Structure (draft)

**`wdl_tasks` collection** — each document stored with:

- **text:** WDL task code (enriched chunk)
- **metadata:**
  - `task_name`
  - `description`
  - `analysis_category` — e.g. `"variant_calling"`
  - `input_types` — e.g. `["FASTQ"]`
  - `output_types` — e.g. `["VCF", "BAM"]`
  - `tools` — structured array with name, version, purpose, and link to docs
  - `docker_images`

**`tool_docs` collection** — each document stored with:

- **text:** Chunked tool documentation (flags, usage, examples)
- **metadata:**
  - `tool_name`
  - `tool_version`

### 7.3 Corpus Curation

**`wdl_tasks` sources:**
- WILDS WDL Library (Fred Hutch)
- Synthetic pipeline examples composed from WILDS WDL Library modules

**`wdl_tasks` target size:**
- 75+ diverse examples (include all existing tasks and pipelines)

**`wdl_tasks` diversity requirements:**
- Major data types (FASTQ, BAM, VCF, BED, CSV, etc.)
- Major analysis types (alignment, variant calling, RNA-seq, QC, etc.)
- Multiple tool approaches for the same analysis

**`tool_docs` sources:**
- Official documentation for all tools referenced in the `wdl_tasks` collection

### 7.4 Embedding Strategy

- Use `sentence-transformers` with `all-MiniLM-L6-v2` (or similar) for both collections. This embedding is the ChromaDB default and is open-source.
- `wdl_tasks`: embed a concatenation of description + metadata fields + partial WDL code
- `tool_docs`: embed chunked documentation text directly; queries are constructed from extracted command-line invocations

## 8. LLM Integration

### 8.1 Model Selection

**Candidates (draft):**
- Llama 3.1 8B Instruct
- Mistral 7B Instruct
- CodeLlama 7B Instruct
- Phi-3 Mini (3.8B)

**Evaluation criteria:**
- Runs on laptop (CPU or GPU)
- WDL syntax correctness
- Instruction following (uses only approved tools)
- Consistency (same inputs → same outputs)
- Inference speed (meets latency targets)

**Selection process:** Test top 3 candidates on a diverse set of inputs; measure validation pass rate and quality; choose the best quality/speed tradeoff.

### 8.2 Inference Configuration

| Parameter | Value |
|---|---|
| Temperature | 0.2 (low, for consistency) |
| Max tokens | 4096 |
| Frequency/presence penalties | None (WDL requires repeated tokens) |

### 8.3 Prompt Strategy

**System prompt:**
- WDL expert persona
- Requirements: valid syntax, follow tool constraints, WILDS WDL Library tasks only
- Output format: WDL code only

**RAG context:**
- Top 3 most similar WDL examples from ChromaDB
- Framed as reference/inspiration, not templates to copy verbatim

**User specifications:**
- Contents of the input form (data types, analysis goals, organism, reference genome, etc.)

**Tool constraints (when human-in-the-loop was used):**
- List of user-approved tools
- Explicit instruction to use these tools and no others

**Retry prompt (on validation failure):**
- Original requirements
- Validation error messages
- Previous WDL attempt
- Instruction to fix the specific errors

### 8.4 LLM Hosting

Local laptop (CPU or GPU via Ollama)

## 9. WDL Validation

**Validation Steps:**

1. **Tool check (Python):** Confirm that user-approved tools — and only those tools — appear in the generated WDL
2. **Syntax check:** `miniwdl check --strict workflow.wdl`
3. **Linting:** `sprocket lint workflow.wdl`

**Retry Logic:**

- On any validation failure, send errors back to the LLM with a correction prompt
- Retry up to 10 times (exact number TBD after testing)
- If all retries fail: return the best attempt along with the remaining errors

## 10. Tool Selection Module

### 10.1 Purpose

Identify and present recommended bioinformatics tools for user review before WDL generation.

### 10.2 Approach (draft)

1. Parse the top-ranked retrieved WDL examples to identify tools
2. Aggregate tools by purpose (alignment, variant calling, etc.)
3. Rank tools by frequency across retrieved examples and retrieval score
4. Validate that all candidates are present in the WILDS WDL Library
5. Present the top tool per purpose, with up to 3 alternatives

### 10.3 Output Format

For each recommended tool:
- Tool name and version
- Purpose in the workflow (e.g., "alignment")
- Link to tool documentation

### 10.4 User Interaction (CLI)

For each tool:
- **Approve** (default) — press 1 to accept
- **Reject** — press 2 to reject, then select from a list of alternatives (or quit if no alternatives)

### 10.5 Integration with WDL Generation

- Approved tools are passed to the LLM prompt as explicit constraints
- Validation step confirms the approved tools (and only those tools) appear in the generated WDL

## 11. Security & Privacy

All components run locally on the developer's laptop. No external service calls.

## 12. Key Design Decisions

### 12.1 Why Human-in-the-Loop?

**Decision:** Require user review at tool selection and final WDL approval.

**Rationale:** Gives users control over tool choice and final output, building trust in the generated workflows.

**Tradeoff:** Adds user review time, but improves confidence in outputs.

### 12.2 Why RAG Instead of Fine-Tuning?

**Decision:** Use RAG with curated examples rather than fine-tuning.

**Rationale:**
- Feasible with current resources — no ML expertise or large WDL training sets required
- Fast, relatively easy to implement, and resource-efficient (no GPU required for indexing)
- Recommended in *AI Engineering* (Chip Huyen) as the right first step before considering fine-tuning

**Tradeoff:** May not perform as well as fine-tuning for edge cases, but RAG is usually sufficient and we can't fine-tune anyway at current resource levels.

### 12.3 Why a Local LLM?

**Decision:** Host the LLM locally via Ollama.

**Rationale:**
- **Cost:** No per-token API fees
- **Privacy:** Research data does not leave the institution
- **Control:** Full control over model selection and configuration

**Tradeoff:** Must manage local infrastructure, but the tool being free and private is a significant plus.

### 12.4 Why No Session History?

**Decision:** Don't persist session history.

**Rationale:**
- Simpler implementation (no file or database management)
- No permission issues
- Users can save the generated WDL for persistence
- Can add session history in a later phase if needed

**Tradeoff:** Users lose context when the script exits, but saving the WDL mitigates this.

### 12.5 Why `all-MiniLM-L6-v2` for Embeddings?

**Decision:** Use `sentence-transformers` with `all-MiniLM-L6-v2` for both collections.

**Rationale:**
- It is the ChromaDB default embedding model and should work well for most cases (including ours)
- This embedding model is open-source

**Tradeoff:** Larger or domain-specific models may produce better embeddings for bioinformatics text, but `all-MiniLM-L6-v2` is a well-established baseline and sufficient for an MVP.


## 13. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| LLM generates invalid WDL | High | Medium | Validation + up to 10 retries; target 100% pass rate |
| LLM ignores approved tools | High | Low | Explicit tool constraints in prompt; validation check before presenting to user |
| Tool recommendations are poor quality | Medium | Medium | Start with example extraction; improve iteratively |
| RAG retrieves irrelevant examples | High | Low | Tune similarity threshold; expand corpus; add metadata filters |
| Inference too slow (>1 hour) | Medium | Medium | Quantized model; optimized prompts |
| Insufficient WDL corpus | High | Medium | Curate 75+ diverse examples |
| Inconsistent outputs | Medium | Medium | Low temperature (0.2); explicit tool constraints; consistency testing |
| Timeline too optimistic | Medium | Medium | Buffer time; scope down if needed; identify critical path early |
| Single developer | Medium | Low | Thorough documentation; managed scope; regular feedback |


## 14. Deliverables
- [ ] LLM model selected (evaluated on test cases)
- [ ] ChromaDB populated with 75 curated WDL examples
- [ ] RAG pipeline functional
- [ ] Validation + retry logic working
- [ ] Tool selection module implemented
- [ ] Input prompts and system prompt finalized
- [ ] Internal testing: 20 test cases


## 15. Future Work (Phase 2+)

- Streamlit web UI (web form, tool review page, WDL display with copy/download)
- Deployment on Fred Hutch cluster (Docker Swarm or equivalent)
- Session history / saved past runs
- Email notification when WDL generation is complete
- Automatic test run against synthetic inputs
- Support for WDL libraries beyond WILDS
- Multi-turn conversational refinement
