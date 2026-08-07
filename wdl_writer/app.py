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
import ui_style

_MODEL = os.environ.get("OLLAMA_MODEL", "granite-code:8b")
_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_MAX_RETRIES = int(os.environ.get("WDL_MAX_RETRIES", 5))
_LOGO_PATH = str(Path(__file__).parent / "assets" / "wilds_logo.jpeg")

st.set_page_config(page_title="WILDS WDL Writer", layout="wide")
ui_style.inject_base_css()
ui_style.render_header(_LOGO_PATH)

# Simple two-stage flow, tracked in session_state so the tool-approval step
# survives the rerun that Streamlit triggers on every widget interaction:
#   "form"     -> collect Q1-Q5 and run keyword filtering
#   "approval" -> human-in-the-loop: approve/reject retrieved tools
#   "done"     -> generation already ran; show results
if "stage" not in st.session_state:
    st.session_state.stage = "form"

ui_style.render_step_indicator(st.session_state.stage)

submitted = False

if st.session_state.stage == "form":
    ui_style.render_caption_card(
        "The WDL Writer is <strong>not a bioinformatician</strong>. You should have an idea what "
        "data you have and the processing steps you need to take."
    )

    with st.form("wdl_inputs"):
        with st.container(border=True):
            ui_style.render_eyebrow("Q1")
            ui_style.render_question("What kind of sequencing data do you have?")
            bio_selections = st.pills(
                "Select one (usually)",
                list(data_type_to_topic.keys()),
                selection_mode="multi",
                label_visibility="collapsed",
            ) or []

        with st.container(border=True):
            ui_style.render_eyebrow("Q2")
            ui_style.render_question("What format(s) will your input data be in?")
            format_selections = st.pills(
                "Select all that apply",
                list(input_format_dict.keys()),
                selection_mode="multi",
                label_visibility="collapsed",
            ) or []

        with st.container(border=True):
            ui_style.render_eyebrow("Q3")
            ui_style.render_question("What species is your data from?")
            species_selections = st.pills(
                "Select one",
                list(species_dict.keys()),
                selection_mode="multi",
                label_visibility="collapsed",
            ) or []

        with st.container(border=True):
            ui_style.render_eyebrow("Q4")
            ui_style.render_question("What processing or analysis do you want done?")
            operation_selections = st.pills(
                "Select all that apply",
                list(operation_topic_dict.keys()),
                selection_mode="multi",
                label_visibility="collapsed",
            ) or []

        with st.container(border=True):
            ui_style.render_eyebrow("Q5", optional=True)
            ui_style.render_question("Any preferred bioinformatics tools?")
            tool_selections = st.multiselect(
                "Select all that apply — start typing to search",
                list(tools_dict.keys()),
                label_visibility="collapsed",
                placeholder="Search tools…",
            )

        _, submit_col = st.columns([5, 1])
        with submit_col:
            submitted = st.form_submit_button("Find relevant tasks →", type="primary")

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
    st.rerun()

if st.session_state.stage == "approval":
    retrieved_ids = st.session_state.retrieved_ids
    available_tools = sorted({task_id.split("_", 1)[0] for task_id in retrieved_ids})

    with st.container(border=True):
        st.markdown('<div class="wdl-card-title">Approve tools</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="wdl-card-desc">Found <strong>{len(retrieved_ids)} relevant task(s)</strong> '
            "from these tools. Tasks from these tools will be given to the LLM for consideration. "
            "Which do you want to keep? Note that some may be important utilities.</div>",
            unsafe_allow_html=True,
        )

        approved_tools = []
        for tool in available_tools:
            task_count = sum(1 for task_id in retrieved_ids if task_id.split("_", 1)[0] == tool)
            checked = ui_style.render_tool_checkbox(tool, task_count, key=f"tool_checkbox_{tool}")
            if checked:
                approved_tools.append(tool)

        col1, col2 = st.columns([1, 5])
        with col1:
            approve_clicked = st.button("Confirm selection", type="primary")
        with col2:
            restart_clicked = st.button("Start over")

    if restart_clicked:
        st.session_state.stage = "form"
        for key in ("keyword_dict", "retrieved_ids"):
            st.session_state.pop(key, None)
        for tool in available_tools:
            st.session_state.pop(f"tool_checkbox_{tool}", None)
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

    with st.container(border=True):
        st.markdown(
            '<div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">'
            '<div style="width:9px; height:9px; border-radius:50%; background:#74c69d;"></div>'
            '<div class="wdl-card-title">Generating WDL workflow</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="wdl-card-desc">Tasks given to the LLM: {", ".join(sorted(confirmed_ids))}</div>',
            unsafe_allow_html=True,
        )

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

    with st.container(border=True):
        header_col, pill_col = st.columns([3, 1])
        with header_col:
            st.markdown('<div class="wdl-card-title">Generated WDL</div>', unsafe_allow_html=True)
        with pill_col:
            if final["valid"]:
                st.markdown(
                    '<div style="text-align:right;"><span class="wdl-status-pill">✓ Validation passed</span></div>',
                    unsafe_allow_html=True,
                )

        if not final["valid"]:
            st.warning("Invalid WDL — showing the best attempt so far. It may need manual fixes before it will run.")
            with st.expander("Validation error"):
                st.code(final["stderr"])

        st.code(final["wdl"], language="wdl")
        st.download_button(
            label="⬇ Download WDL",
            data=final["wdl"],
            file_name="workflow.wdl",
            mime="text/plain",
            type="primary",
        )

        if st.button("Start a new workflow"):
            prior_tools = {
                task_id.split("_", 1)[0] for task_id in st.session_state.get("retrieved_ids", [])
            }
            for key in ("stage", "keyword_dict", "retrieved_ids", "confirmed_ids", "final_result"):
                st.session_state.pop(key, None)
            for tool in prior_tools:
                st.session_state.pop(f"tool_checkbox_{tool}", None)
            st.rerun()

        st.markdown(
            '<div class="wdl-footer">For help running your WDL, contact OCDO via '
            '<a href="https://ocdo.fredhutch.org/programs/data-house-calls.html">Data House Calls</a>.</div>',
            unsafe_allow_html=True,
        )
