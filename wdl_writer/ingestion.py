import chromadb
import os
import re

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WDL_DIR = os.path.join(THIS_DIR, "..", "data", "wdl")
DEFAULT_CHROMA_DIR = os.path.join(THIS_DIR, "..", "data", "chroma")


def get_tasks(wdl: str, toolname: str) -> list[tuple[dict, str]]:
    """Extract individual WDL tasks from a WDL file string

    Use regex to identify tasks within a wdl and store each
    in a tuple with basic metadata.

    Returns a list of (metadata_dict, task_text) tuples, one per task.
    """
    tasks = []
    lines = wdl.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        match = re.match(r'^task\s+(\w+)\s*\{', lines[i])
        if match:
            task_name = match.group(1)
            depth = 0
            start = i
            while i < len(lines):
                depth += lines[i].count('{') - lines[i].count('}')
                i += 1
                if depth == 0:
                    break
            wdl_task = ''.join(lines[start:i])
            wdl_meta = {"tool": toolname, "task": task_name}
            tasks.append((wdl_meta, wdl_task))
        else:
            i += 1
    return tasks


def parse_meta(task: str) -> dict:
    """Extract relevant metadata from a WDL task

    Extract and parse custom metadata tags and format them to be used 
    for ChromaDB document metadata. These tags use EDAM ontology terms and the 
    tags describing the task's File parameters are formatted as:

    <param_name>:<EDAM_data_type>:<EDAM_format_type>

    When multiple File formats are acceptable for the same parameter, those 
    formats are separated by "|". E.g.:

    input_aln:nucleic_acid_sequence_alignment:bam|sam|cram
    """
    extracted_meta = {}

    meta_match = re.search(r'meta\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', task, re.DOTALL)
    if not meta_match:
        return {}
    meta_block = meta_match.group(1)

    for tag in ['topic', 'species', 'operation']:
        full_line = re.search(rf'^\s+{tag}:\s+"([^"]+)"', meta_block, re.MULTILINE)
        if full_line:
            extracted_meta[tag] = full_line.group(1).split(',')

    # These File-type tags are comma-separated <parameter_name>:<EDAM
    for tag in ['input_sample_required', 'output_sample']:
        full_line = re.search(rf'^\s+{tag}:\s+"([^"]+)"', meta_block, re.MULTILINE)
        if not full_line:
            continue
        param_substrings = [param.split(":") for param in full_line.group(1).split(",")]
        if param_substrings[0][0] == 'none':
            param_data = ['none']
            param_format = ['none']
        else:
            param_data = list({p[1] for p in param_substrings})
            format_intermed = [p[2].split('|') for p in param_substrings]
            param_format = list(set(sum(format_intermed, [])))
        if tag == 'input_sample_required':
            extracted_meta['input_sample_data_types'] = param_data
            extracted_meta['input_sample_format_types'] = param_format
        else:
            extracted_meta['output_sample_data_types'] = param_data

    return extracted_meta


def load_wdl_tasks(wdl_dir: str = DEFAULT_WDL_DIR) -> list[tuple[dict, str]]:
    """Parse all WDLs in wdl_dir and return (metadata, task_text) tuples
    
    Parse all .wdl files in wdl_dir, using get_tasks() to extract tasks from 
    each file and parse_meta() to turn metadata blocks into a format for 
    ChromaDB.
    """
    metas_tasks = []
    for filename in os.listdir(wdl_dir):
        if not filename.endswith('.wdl'):
            continue
        # Ignore our WDLs used for examples and testing
        if filename in ['ww-template.wdl', 'ww-testdata.wdl']:
            continue
        toolname = filename[3:-4]  # strip 'ww-' prefix and '.wdl' suffix
        with open(os.path.join(wdl_dir, filename)) as f:
            content = f.read()
        tasks = get_tasks(content, toolname)
        for meta, task_text in tasks:
            meta.update(parse_meta(task_text))
        metas_tasks.extend(tasks)
    return metas_tasks


def update_collection(
    metas_tasks: list[tuple[dict, str]],
    chroma_dir: str = DEFAULT_CHROMA_DIR,
    collection_name: str = "wdl_tasks") -> dict:
    """Ingest WDL tasks from wdl_dir into a ChromaDB collection

    Safe to re-run: uses upsert so existing records are updated rather than
    duplicated. Returns a summary dict with task and collection counts.
    """
    metadatas, documents = zip(*metas_tasks)
    ids = [f'{meta["tool"]}_{meta["task"]}' for meta in metadatas]

    # Initiate a collection and save to the `data/` folder
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(name=collection_name)
    collection.upsert(
        ids=ids,
        documents=list(documents),
        metadatas=list(metadatas),
    )
    # Number of items in our collection now
    return collection.count()


if __name__ == "__main__":
    metas_tasks = load_wdl_tasks()
    collection_count = update_collection(metas_tasks)
    num_tasks = len(metas_tasks)
    print(f"WDL tasks ingested: {num_tasks}")
    print(f"Tasks in collection: {collection_count}")
    print(f"Same number of tasks ingested and in collection: {num_tasks == collection_count}")
