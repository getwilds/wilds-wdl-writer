# wilds-wdl-writer

> ⚠️ **Under Construction** — This tool is actively in development and is incomplete, unstable, and subject to breaking changes. Not intended for use at this time.

An LLM-based tool for building custom WDL workflows using validated components from the WILDS WDL Library.

This repository is the **Minimum Viable Product (MVP)** of a larger planned project. The final product is intended to be a point-and-click web application running on the Fred Hutch cluster, making WDL workflow generation accessible to users without requiring any local setup or command-line experience.

To learn more, read the [Design Specifications](docs/mvp_design_spec.md)

---

Requirements (so far):
- `pandas`
- `numpy`
- `chromadb`
- `ollama`
- `rapidfuzz`
- `llama-index-core`
- `llama-index-embeddings-huggingface`

---
### Schema

![Schema](docs/wdl_writer_0205.png)
