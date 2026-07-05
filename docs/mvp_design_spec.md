# MVP Design Spec: WILDS WDL Writer

**Author:** Emma Bishop

**Last modified:** 2026-04-01

**Status:** Draft

**Version:** 1.0.1

**Reviewers:** (casually) Taylor Firman and Robert McDermott

## Table of Contents

1. [Overview](#1-overview)
   - [1.1 Purpose and Problem Statement](#11-purpose-and-problem-statement)
   - [1.2 Users](#12-users)
   - [1.3 Scope](#13-scope)
2. [Success Criteria](#2-success-criteria)
3. [User Flow](#3-user-flow)
4. [Data Flow](#4-data-flow)
5. [System Architecture](#5-system-architecture)
   - [5.1 Components](#51-components)
   - [5.2 Technology Stack](#52-technology-stack)
6. [ChromaDB Vector Database](#6-chromadb-vector-database)
   - [6.1 Document Structure](#61-document-structure)
7. [LLM Integration](#7-llm-integration)
   - [7.1 Model Selection](#71-model-selection)
   - [7.2 Inference Configuration](#72-inference-configuration)
   - [7.3 Prompt Strategy](#73-prompt-strategy)
   - [7.4 LLM Hosting](#74-llm-hosting)
8. [WDL Validation](#8-wdl-validation)
9. [Tool Selection Module](#9-tool-selection-module)
10. [Security & Privacy](#10-security--privacy)
11. [Key Design Decisions](#11-key-design-decisions)
    - [11.1 Why a Local LLM?](#111-why-a-local-llm)
    - [11.2 Why RAG Instead of Fine-Tuning?](#112-why-rag-instead-of-fine-tuning)
    - [11.3 Why Human-in-the-Loop?](#113-why-human-in-the-loop)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Deliverables](#13-deliverables)
14. [Future Work](#14-future-work)

---

## 1. Overview

### 1.1 Purpose and Problem Statement

**Purpose:**

WILDS WDL Writer is a local, LLM-based command-line tool for generating complete WDL (Workflow Description Language) workflows using components from the [WILDS WDL Library](https://github.com/getwilds/wilds-wdl-library). Users provide information about their input data and analysis goals via an interactive CLI session. The tool uses RAG (Retrieval-Augmented Generation) to search through curated WDL examples and identify appropriate componenents, which provide context to the language model. The tool incorporates human-in-the-loop approval when selecting bioinformatics tools and when reviewing the final WDL output.

**Problem Statement:**

WDL workflows take a long time to write and require significant bioinformatics knowledge. These problems are experienced by both new and experienced WDL users and are a barrier to WDL adoption by labs.

### 1.2 Users

Bioinformaticians (primary) and postdocs and grad students (secondary).

**User Needs:**
- Able to write WDLs for their use cases
- Faster and/or easier than iterating with an AI chatbot (e.g., ChatGPT, Claude)

**User Stories:**

- **US-1 Faster Than Manual Writing:** As a grad student creating a variant calling workflow, I want to generate a complete WDL in under an hour so that I can be more productive than writing it manually or iterating with ChatGPT.
- **US-2 Privacy Requirements:** As a researcher developing unpublished pipelines, I want to generate workflows without sending any information outside Fred Hutch so that I can use it with unpublished or sensitive pipeline designs.
- **US-3 WDL Validation:** As a user generating a WDL from scratch, I want to validate its syntax so that I can run it without error.

### 1.3 Scope

**In Scope:**

- Interactive CLI for collecting user inputs
- RAG retrieval over curated WILDS WDL Library examples and tool documentation
- Human-in-the-loop tool bioinformatics approval checkpoint
- WDL generation using a local LLM
- WDL validation with automatic retry
- Human-in-the-loop final review and save to disk
- Basic Streamlit web UI as a first-draft alternative to the CLI (same underlying pipeline; not yet feature-complete — see Section 14 for planned improvements)

**Out of Scope:**

- Fine-tuning LLMs
- Cloud or cluster execution
- Workflow execution (users run WDLs themselves)
- History or storage of past sessions

## 2. Success Criteria

| Metric | Target |
|---|---|
| Syntax correctness | 100% (20/20) of generated WDLs pass `miniwdl` and `sprocket` validation |
| Functional correctness | 95% (19/20) of generated WDLs use appropriate tools and parameters |
| Latency: tool plan to user | <15 seconds |
| Latency: full WDL generation | <1 hour |
| Consistency (same inputs, same output) | ≥80% identical. Non-identical outputs ≥85% lexical similarity and ≥90% pairwise cosine similarity |

**Latency Budget:**

| Stage | Target |
|---|---|
| Input collection | Interactive (user-paced) |
| RAG retrieval | <5 seconds |
| Tool selection presentation | <15 seconds |
| WDL generation | <1 hour |
| Validation | <3 minutes |
| **Total (no human review time)** | **<1 hour** |



## 3. User Flow

1. User runs the script and is prompted to select from pre-written values for:
   - Input data types (e.g. "Paired FASTQ")
   - Analysis goals (e.g. "Variant Calling")
   - Optional: Preferred tools (e.g. "GATK")
2. System retrieves relevant WDL examples and tool documentation and extracts bioinformatics tool recommendations
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


## 4. Data Flow

**Step 1: Input Collection**

- Prompt user for required and optional fields
- Validate that required fields are present and that inputs are mutually compatible
- If validation fails, surface a clear error; otherwise proceed

**Step 2: RAG Retrieval**

1. Query the ChromaDB collection of WDL tasks using metadata filters (analysis category, input/output types)
2. For each retrieved task, extract command-line invocations from the command block 
3. Use command blocks to query the tool documentation collection via vector search
4. Retrieved context includes metadata-enriched task chunks and relevant tool documentation

**Step 3: Tool Selection**

- Parse retrieved examples to identify candidate tools
- Present tool list to user with documentation links and alternatives
- Wait for user approval/modifications

**Step 4: Prompt Construction**

Combine into a single LLM prompt:
- System prompt (WDL generation instructions)
- Retrieved WDL examples and tool documentation (RAG context)
- User input information
- Approved tool list

**Step 5: WDL Generation**

- Send prompt to local LLM
- Display progress message

**Step 6: Validation & Retry**

1. Confirm that user-approved tools (and only those tools) appear in the WDL
   - If invalid: send back to LLM with a correction prompt
2. Run linting (`sprocket lint`) and validation (`miniwdl check --strict`)
   - If valid: proceed
   - If invalid: send validation errors back to LLM with a retry prompt; repeat up to 10 times
   - If all retries fail: return best attempt with errors attached

**Step 7: Final Review**

- Display WDL in terminal (in a way user can easily copy/paste)
- Prompt user to approve or reject
  - **Approve:** save to disk at user specified location
  - **Reject:** collect reason; retry generation once with that feedback appended to the prompt


## 5. System Architecture

### 5.1 Components

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

### 5.2 Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| RAG framework | [LlamaIndex](https://www.llamaindex.ai/) | `VectorStoreIndex`, `PromptTemplate`, `CustomQueryEngine`, `Ollama` integration |
| Vector database | [ChromaDB](https://www.trychroma.com/) | Local, no server required |
| Embeddings | [`sentence-transformers`](https://sbert.net/) | `all-MiniLM-L6-v2` or similar |
| LLM runtime | [Ollama](https://ollama.com/) | Runs models locally; no external API calls |
| LLM model | TBD | Evaluated on WDL generation quality and speed |
| WDL validation | `miniwdl`, `sprocket` | Could possibly just use sprocket |
| CLI | `click` | Can display options for user to enter |

---

## 6. ChromaDB Vector Database

Two ChromaDB collections support the RAG pipeline:

- **`wdl_tasks`** — stores enriched WDL task chunks from the WILDS WDL Library. The primary retrieval mechanism is metadata filtering (analysis category, input/output types); vector search is available as a fallback when metadata filters return insufficient results.
- **`tool_docs`** — stores chunked tool documentation. Queried via vector search using command-line invocations extracted from a retrieved task's command block.

### 6.1 Document Structure

**`wdl_tasks` collection** — each document stored with:

- **text:** WDL scripts chunked by task
- **metadata:**
  - `tool` - e.g. `"strelka"`
  - `task` - e.g. `"strelka_germline"`
  - `topic` - e.g. `["genomics", "dna_polymorphism"]`
  - `species` - e.g. `["eukaryote"]`
  - `operation` - e.g. `"variant_calling"`
  - `input_sample_data_types` - e.g. `["nucleic_acid_sequence_alignment", "data_index"]`
  - `input_sample_format_types` - e.g. `["bam", "bai"]`
  - `output_sample_data_types` - e.g. `["sequence_variations", "data_index"]`

**`tool_docs` collection** — each document stored with:

- **text:** Tool documentation chunked by tool command
- **metadata:**
  - `tool`

**Embedding Strategy**

Use `sentence-transformers` with `all-MiniLM-L6-v2` for `tool_docs` collection.

## 7. LLM Integration

### 7.1 Model Selection

**Candidates (draft):**
- Llama 3.1 8B Instruct
- Mistral 7B Instruct
- CodeLlama 7B Instruct
- Phi-3 Mini (3.8B)

Check Fred Hutch policies and Data Governance guidelines around model choice. Some are blacklisted for security reasons.

**Evaluation criteria:**
- Runs on laptop (GPU via [Apple M chips](https://www.apple.com/macbook-air/specs/))
- WDL syntax correctness
- Instruction following (uses only approved tools)
- Consistency (same inputs → same outputs)
- Inference speed (meets latency targets)

**Selection process:** Test top 3 candidates on a diverse set of inputs; measure validation pass rate and quality; choose the best quality/speed tradeoff.

### 7.2 Inference Configuration

| Parameter | Value |
|---|---|
| Temperature | 0.2 (low, for consistency) |
| Max tokens | 4096 |
| Frequency/presence penalties | None (WDL requires repeated tokens) |

Note that while 4096 tokens isn't a lot, it should be sufficient for providing WDL task context to the LLM. We are not storing chat history level context.

### 7.3 Prompt Strategy

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

### 7.4 LLM Hosting

Local laptop (GPU via [Apple M chips](https://www.apple.com/macbook-air/specs/))

## 8. WDL Validation

**Validation Steps:**

1. **Tool check (Python):** Confirm that user-approved tools — and only those tools — appear in the generated WDL
2. **Syntax check:** `miniwdl check --strict workflow.wdl`
3. **Linting:** `sprocket lint workflow.wdl`

**Retry Logic:**

- On any validation failure, send errors back to the LLM with a correction prompt
- Retry up to 10 times (exact number TBD after testing, 10 may be high)
- If all retries fail: return the best attempt along with the remaining errors

## 9. Tool Selection Module

Identify and present recommended bioinformatics tools for user review before WDL generation.

1. Parse the top-ranked retrieved WDL task metadata to identify tools
2. Aggregate tools by purpose (alignment, variant calling, etc.). Store up to three alternatives.
3. Present the top tool per purpose, along with category and documentation
4. Users must approve or reject each tool. Alternatives are presented for rejected tools.
5. Approved tools are passed to the LLM prompt as explicit constraints
6. Validation step confirms the approved tools (and only those tools) appear in the generated WDL

## 10. Security & Privacy

All components run locally on the developer's laptop. No external service calls.

## 11. Key Design Decisions

### 11.1 Why a Local LLM?

**Decision:** Host the LLM locally via Ollama.

**Rationale:**
- **Cost:** No per-token API fees
- **Privacy:** Research data does not leave the institution
- **Control:** Full control over model selection and configuration

**Tradeoff:** Must manage local infrastructure, but the tool being free and private is a significant plus.


### 11.2 Why RAG Instead of Fine-Tuning?

**Decision:** Use RAG with curated examples rather than fine-tuning.

**Rationale:**
- Feasible with current resources — no ML expertise or large WDL training sets required
- Fast, relatively easy to implement, and resource-efficient (no GPU required for indexing or metadata filtering)
- Recommended in *AI Engineering* (Chip Huyen) as the right first step before considering fine-tuning

**Tradeoff:** May not perform as well as fine-tuning for edge cases, but RAG is usually sufficient and we can't fine-tune anyway at current resource levels.


### 11.3 Why Human-in-the-Loop?

**Decision:** Require user review at tool selection and final WDL approval.

**Rationale:** Gives users control over tool choice and final output, building trust in the generated workflows.

**Tradeoff:** Adds user review time, but improves confidence in outputs.

## 12. Risks & Mitigations

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


## 13. Deliverables
- [ ] LLM model selected (evaluated on test cases)
- [ ] ChromaDB populated with 75 curated WDL examples
- [ ] RAG pipeline functional
- [ ] Validation + retry logic working
- [ ] Tool selection module implemented
- [ ] Input prompts and system prompt finalized
- [ ] Internal testing: 20 test cases


## 14. Future Work

- Streamlit UI polish: tool review/approval checkpoint (currently CLI-only), editable final review before download
- Deployment on Fred Hutch cluster (Docker Swarm or equivalent)
- Session history / saved past runs
- Email notification when WDL generation is complete
- Automatic test run against synthetic inputs
- Support for WDL libraries beyond WILDS
- Multi-turn conversational refinement
