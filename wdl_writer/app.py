"""Streamlit web interface for the WILDS WDL Writer."""

import sys
import os
from pathlib import Path

import streamlit as st
from ollama import Client

sys.path.insert(0, str(Path(__file__).parent))

from user_interface_dicts import (
    data_type_to_topic,
    input_format_dict,
    species_dict,
    operation_topic_dict,
    tools_dict,
)
from user_interface import filter_keywords_for_tasks
from retrieval import retrieve_tasks
from prompts import build_system, build_user
from generation import extract_wdl, validate_wdl, build_retry

_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_MAX_RETRIES = int(os.environ.get("WDL_MAX_RETRIES", 5))

st.set_page_config(page_title="WILDS WDL Writer", layout="wide")
st.title("WILDS WDL Writer")
st.caption(
    "The WDL Writer is **not a bioinformatician**. You should have an idea what "
    "data you have and the processing steps you need to take."
)

# Simple two-stage flow, tracked in session_state so the tool-approval step
# survives the rerun that Streamlit triggers on every widget interaction:
#   "form"     -> collect Q1-Q5 and run keyword filtering
#   "approval" -> human-in-the-loop: approve/reject retrieved tools
#   "done"     -> generation already ran; show results
if "stage" not in st.session_state:
    st.session_state.stage = "form"

with st.form("wdl_inputs"):
    st.subheader("Q1: What kind of sequencing data do you have?")
    bio_selections = st.multiselect("Select one (usually)", list(data_type_to_topic.keys()))

    st.subheader("Q2: What format(s) will your input data be in?")
    format_selections = st.multiselect("Select all that apply", list(input_format_dict.keys()))

    st.subheader("Q3: What species is your data from?")
    species_selections = st.multiselect("Select one", list(species_dict.keys()))

    st.subheader("Q4: What processing or analysis do you want done?")
    operation_selections = st.multiselect("Select all that apply", list(operation_topic_dict.keys()))

    st.subheader("Q5: Any preferred bioinformatics tools? (optional)")
    tool_selections = st.multiselect("Select all that apply", list(tools_dict.keys()))

    submitted = st.form_submit_button("Find relevant tasks")

if submitted:
    # Validate required fields
    if not bio_selections:
        st.error("Please select at least one sequencing data type (Q1).")
        st.stop()
    if not format_selections:
        st.error("Please select at least one input format (Q2).")
        st.stop()
    if not species_selections:
        st.error("Please select a species (Q3).")
        st.stop()
    if not operation_selections:
        st.error("Please select at least one operation (Q4).")
        st.stop()

    # Build keyword dict in the same structure user_interface.py produces
    def _collect(d, keys, slot):
        terms = []
        for k in keys:
            terms += d[k][slot]
        return list(set(terms))

    keyword_dict = {
        "bio_topic": _collect(data_type_to_topic, bio_selections, 0),
        "op_topic": _collect(operation_topic_dict, operation_selections, 1),
        "format": _collect(input_format_dict, format_selections, 0),
        "species": _collect(species_dict, species_selections, 0),
        "operation": _collect(operation_topic_dict, operation_selections, 0),
        "tool": _collect(tools_dict, tool_selections, 0),
    }

    confirmed_ids = filter_keywords_for_tasks(keyword_dict)

    if not confirmed_ids:
        st.error("No tasks available for this combination of inputs. Try broadening your selections.")
        st.stop()

    # Stash inputs for the approval/generation stages and advance
    st.session_state.keyword_dict = keyword_dict
    st.session_state.retrieved_ids = confirmed_ids
    st.session_state.stage = "approval"

if st.session_state.stage == "approval":
    retrieved_ids = st.session_state.retrieved_ids
    available_tools = sorted({task_id.split("_", 1)[0] for task_id in retrieved_ids})

    st.subheader("Approve tools")
    st.write(
        f"Found {len(retrieved_ids)} relevant task(s) from these tools. Tasks from these tools "
        "will be given to the LLM for consideration. Which do you want to keep? "
        "Note that some may be important utilities."
    )
    approved_tools = st.multiselect(
        "Tools to keep",
        available_tools,
        default=available_tools,
        key="approved_tools",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        approve_clicked = st.button("Confirm selection", type="primary")
    with col2:
        restart_clicked = st.button("Start over")

    if restart_clicked:
        st.session_state.stage = "form"
        for key in ("keyword_dict", "retrieved_ids", "approved_tools"):
            st.session_state.pop(key, None)
        st.rerun()

    if approve_clicked:
        if not approved_tools:
            st.error(
                "It seems we don't have the tools you would prefer. Try going back and making "
                "different selections, or request tools be added to the WILDS WDL Library by "
                "filing an issue: https://github.com/getwilds/wilds-wdl-library"
            )
            st.stop()

        approved_ids = {
            task_id for task_id in retrieved_ids if task_id.split("_", 1)[0] in approved_tools
        }
        st.session_state.confirmed_ids = approved_ids
        st.session_state.stage = "generate"
        st.rerun()

    st.stop()

if st.session_state.stage == "generate":
    keyword_dict = st.session_state.keyword_dict
    confirmed_ids = st.session_state.confirmed_ids

    st.info(f"Tasks that will be given to the LLM: {', '.join(sorted(confirmed_ids))}")

    retrieved_examples = retrieve_tasks(", ".join(confirmed_ids))

    system_prompt = build_system(
        include_spec=True,
        include_example=True,
        include_wilds=True,
        retrieved_examples=retrieved_examples,
    )
    template_vars = {
        "tasks": ", ".join(confirmed_ids),
        "input_data_type": ", ".join(keyword_dict["bio_topic"]),
        "format": ", ".join(keyword_dict["format"]),
        "species": ", ".join(keyword_dict["species"]),
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user(template_vars)},
    ]

    client = Client(host=_HOST)

    with st.status("Generating WDL workflow (this may take a while)...", expanded=True) as status:
        attempts = []
        for attempt_idx in range(_MAX_RETRIES + 1):
            st.write(f"Attempt {attempt_idx + 1} of {_MAX_RETRIES + 1}: generating...")
            chunks = []
            for chunk in client.chat(model=_MODEL, messages=messages, stream=True):
                chunks.append(chunk["message"]["content"])
            raw = "".join(chunks)

            st.write("Validating...")
            wdl = extract_wdl(raw)
            check = validate_wdl(wdl)
            attempts.append({"valid": check["valid"], "stderr": check["stderr"], "wdl": wdl})

            if check["valid"]:
                st.write("Validation passed!")
                break
            elif attempt_idx < _MAX_RETRIES:
                with st.expander(f"Validation failed — attempt {attempt_idx + 1}"):
                    st.code(check["stderr"])
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": build_retry(check["stderr"])})
            else:
                with st.expander(f"Validation failed after all retries — attempt {attempt_idx + 1}"):
                    st.code(check["stderr"])

        final = attempts[-1]
        status.update(
            label="Done! Validation passed." if final["valid"] else "Done (validation failed — best attempt shown).",
            state="complete" if final["valid"] else "error",
        )

    st.session_state.final_result = final
    st.session_state.stage = "done"
    st.rerun()

if st.session_state.stage == "done":
    final = st.session_state.final_result

    if not final["valid"]:
        st.warning("Invalid WDL — showing the best attempt so far. It may need manual fixes before it will run.")
        with st.expander("Validation error"):
            st.code(final["stderr"])

    st.subheader("Generated WDL")
    st.code(final["wdl"], language="wdl")
    st.download_button(
        label="Download WDL",
        data=final["wdl"],
        file_name="workflow.wdl",
        mime="text/plain",
    )

    st.markdown(
        "For help running your WDL, contact OCDO via "
        "[Data House Calls](https://ocdo.fredhutch.org/programs/data-house-calls.html)."
    )

    if st.button("Start a new workflow"):
        for key in ("stage", "keyword_dict", "retrieved_ids", "approved_tools", "confirmed_ids", "final_result"):
            st.session_state.pop(key, None)
        st.rerun()
