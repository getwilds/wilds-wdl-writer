# wilds-wdl-writer

An LLM-based tool for building custom WDL workflows using validated components from the [WILDS WDL Library](https://github.com/getwilds/wilds-wdl-library).

This repository is the **Minimum Viable Product (MVP)** of a larger planned project. The final product is intended to be a point-and-click web application running on the Fred Hutch cluster, making WDL workflow generation accessible to users without requiring any local setup or command-line experience.


## Disclaimer: performance and trustworthiness

The WDL Writer is **not a bioinformatician**. It assembles workflows only from existing WILDS WDL Library module tasks. The user must define the operations needed (e.g. alignment, variant calling) and approve potential WILDS WDL modules to consider. It uses a local LLM whose output quality varies. **Always review the generated WDL carefully before running it on real data.**


### Schema

![Schema](docs/wdl_writer_0205.png)


## Requirements

- Python 3.13+
- [Ollama](https://ollama.com/) running locally (or reachable via `OLLAMA_HOST`), with a model pulled (default: `llama3.2:3b`, configurable via `OLLAMA_MODEL`)
- `numpy`
- `chromadb`
- `ollama`
- `rapidfuzz`
- `streamlit`
- `sentence-transformers` (only needed for benchmarking)


## Running locally

1. Clone the repo and install dependencies:
   ```bash
   $ git clone https://github.com/getwilds/wilds-wdl-writer
   $ cd wilds-wdl-writer
   $ uv pip install numpy chromadb ollama rapidfuzz streamlit
   ```
2. Make sure Ollama is installed and running, and that you've pulled a model:
   ```bash
   $ ollama serve &
   $ ollama pull llama3.2:3b
   ```
3. Run the interactive CLI:
   ```bash
   $ python3 wdl_writer/generate_wdl.py
   ```
   You'll be prompted for your input data type, format, species, and desired analysis steps, then asked to approve which tools to include before the final WDL is generated.

To point at a different Ollama host/model, set `OLLAMA_HOST` and `OLLAMA_MODEL` before running.


## Running on the Fred Hutch cluster (Chorus)

The tool can also be run on Fred Hutch's Chorus GPU nodes, using an Apptainer-packaged Ollama server for inference. See [`scripts/ChorusGenerateWDL.sh`](scripts/ChorusGenerateWDL.sh) for the full walkthrough, which covers:

1. Pulling the `getwilds/ollama` Apptainer image
2. Starting an interactive GPU session on the `chorus` partition
3. Launching the Ollama server inside the container and pulling/configuring the model
4. Running `generate_wdl.py` against that local Ollama server

Fred Hutch and consortium users can schedule a [Research Computing and Data Management Data House Call](https://ocdo.fredhutch.org/programs/dhc.html#research-computing-and-data-management) for help getting set up on the cluster.


## Running the Streamlit app

A web UI (`wdl_writer/app.py`) wraps the same pipeline in a form-based Streamlit interface instead of the interactive CLI.

**Locally:**
```bash
cd wdl_writer
streamlit run app.py
```
Then open the URL Streamlit prints (typically `http://localhost:8501`).

**On the cluster:** submit [`scripts/ChorusStreamlit.sbatch`](scripts/ChorusStreamlit.sbatch) from rhino:
```bash
sbatch scripts/ChorusStreamlit.sbatch
```
This sets up a venv, launches Ollama on a Chorus GPU node, and starts Streamlit. Watch the job log for a banner with the SSH tunnel command to run on your laptop and the local URL to open in your browser. (See also [`scripts/ChorusStreamlit.sh`](scripts/ChorusStreamlit.sh) for the equivalent interactive, non-`sbatch` version.)

---

## Getting help

- **Fred Hutch and consortium users:** can get hands-on help via [Data House Calls](https://ocdo.fredhutch.org/programs/dhc.html#research-computing-and-data-management).
- **Missing or incorrect WDL tasks:** the WDL Writer can only use tools that exist in the [WILDS WDL Library](https://github.com/getwilds/wilds-wdl-library). If a tool you need is missing, [file an issue](https://github.com/getwilds/wilds-wdl-library/issues) there.
- **Bugs or feature requests for this tool:** [file an issue](https://github.com/getwilds/wilds-wdl-writer/issues) in this repository. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute changes.
