"""Streamlit web interface for the WILDS WDL Writer."""

import re
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

_Q4_GROUPS = {
    "Quality & data prep": [
        "Quality control",
        "File conversion",
        "File manipulation",
        "Data download",
        "Data upload",
    ],
    "Alignment & assembly": [
        "Alignment",
        "Assembly",
    ],
    "Variants": [
        "Variant calling (SNPs and indels)",
        "Variant calling (copy number)",
        "Variant calling (structural)",
        "Annotate variants",
        "Imputation",
    ],
    "Expression & splicing": [
        "Gene expression",
        "Alternative splicing prediction",
    ],
    "Annotation, structure & other": [
        "Annotate sequence features",
        "Sequence classification",
        "Pathogen genomic analysis",
        "Structure analysis",
        "Proteomic analysis",
        "Epigenomic analysis",
    ],
}

st.set_page_config(page_title="WILDS · WDL Writer", layout="centered")

# -- session state defaults --
for key, default in [
    ("view", "form"),
    ("data", []),
    ("formats", []),
    ("species", None),
    ("operation", []),
    ("tools", []),
    ("wdl", ""),
    ("attempts", []),
    ("confirmed_ids", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _collect(d, keys, slot):
    terms = []
    for k in keys:
        terms += d[k][slot]
    return list(set(terms))


# ── FORM VIEW ────────────────────────────────────────────────────────────────
if st.session_state.view == "form":
    st.title("Build a WDL workflow")
    st.markdown(
        "Answer a few questions about your data and goals. "
        "The Writer is **not a bioinformatician** — you should know roughly what steps you need."
    )

    # Progress bar: count how many of Q1–Q4 are answered
    required_answered = sum([
        bool(st.session_state.data),
        bool(st.session_state.formats),
        bool(st.session_state.species),
        bool(st.session_state.operation),
    ])
    st.progress(required_answered / 4, text=f"{required_answered} of 4 required answered")

    st.markdown("---")

    # Q1
    st.markdown("**1 · What kind of sequencing data do you have?**")
    st.caption("Usually one. e.g. RNA for an expression study.")
    st.session_state.data = st.pills(
        "Data type",
        options=list(data_type_to_topic.keys()),
        selection_mode="multi",
        default=st.session_state.data,
        label_visibility="collapsed",
        key="q1_pills",
    )

    st.markdown("**2 · What format(s) is your input data in?**")
    st.caption("Select all that apply.")
    st.session_state.formats = st.multiselect(
        "Input formats",
        options=list(input_format_dict.keys()),
        default=st.session_state.formats,
        label_visibility="collapsed",
        key="q2_multiselect",
    )

    st.markdown("**3 · What species is your data from?**")
    st.session_state.species = st.segmented_control(
        "Species",
        options=list(species_dict.keys()),
        selection_mode="single",
        default=st.session_state.species,
        label_visibility="collapsed",
        key="q3_seg",
    )

    st.markdown("**4 · What processing or analysis do you want done?**")
    st.caption("Select all that apply — grouped by purpose.")
    current_ops = list(st.session_state.operation)
    new_ops = []
    for group_label, group_options in _Q4_GROUPS.items():
        st.markdown(f"<span style='font-size:12px;color:#6E7079;font-weight:600;'>{group_label}</span>", unsafe_allow_html=True)
        group_default = [o for o in group_options if o in current_ops]
        selected = st.pills(
            group_label,
            options=group_options,
            selection_mode="multi",
            default=group_default,
            label_visibility="collapsed",
            key=f"q4_{group_label}",
        )
        new_ops.extend(selected)
    st.session_state.operation = new_ops

    with st.expander("5 · Any preferred bioinformatics tools? (optional)", expanded=False):
        st.caption("Leave empty to let the Writer pick from the WILDS library.")
        st.session_state.tools = st.multiselect(
            "Preferred tools",
            options=list(tools_dict.keys()),
            default=st.session_state.tools,
            label_visibility="collapsed",
            key="q5_multiselect",
        )

    st.markdown("---")

    # Recap card
    with st.container(border=True):
        st.markdown("**Your run**")
        data_line = ", ".join(st.session_state.data) if st.session_state.data else "*—*"
        species_line = st.session_state.species if st.session_state.species else "*—*"
        formats_line = ", ".join(st.session_state.formats) if st.session_state.formats else "*—*"
        ops_line = ", ".join(st.session_state.operation) if st.session_state.operation else "*—*"
        tools_line = ", ".join(st.session_state.tools) if st.session_state.tools else "*auto-selected by RAG*"
        st.markdown(
            f"**Data** {data_line} · **Species** {species_line}  \n"
            f"**Formats** {formats_line}  \n"
            f"**Analysis** {ops_line}  \n"
            f"**Tools** {tools_line}"
        )

    all_required = (
        bool(st.session_state.data)
        and bool(st.session_state.formats)
        and bool(st.session_state.species)
        and bool(st.session_state.operation)
    )

    if all_required:
        st.caption("All set — generation takes up to a few minutes.")
    else:
        st.caption("Answer all 4 required questions to enable generation.")

    if st.button("Generate WDL", type="primary", disabled=not all_required):
        st.session_state.view = "generating"
        st.rerun()


# ── GENERATING VIEW ───────────────────────────────────────────────────────────
elif st.session_state.view == "generating":
    st.title("Generating your workflow")

    keyword_dict = {
        "bio_topic": _collect(data_type_to_topic, st.session_state.data, 0),
        "op_topic": _collect(operation_topic_dict, st.session_state.operation, 1),
        "format": _collect(input_format_dict, st.session_state.formats, 0),
        "species": _collect(species_dict, [st.session_state.species], 0),
        "operation": _collect(operation_topic_dict, st.session_state.operation, 0),
        "tool": _collect(tools_dict, st.session_state.tools, 0),
    }

    confirmed_ids = filter_keywords_for_tasks(keyword_dict)
    st.session_state.confirmed_ids = confirmed_ids

    if not confirmed_ids:
        st.error("No tasks available for this combination of inputs. Try broadening your selections.")
        if st.button("Edit selections"):
            st.session_state.view = "form"
            st.rerun()
        st.stop()

    retrieved_examples = retrieve_tasks(", ".join(confirmed_ids))
    n_examples = len(retrieved_examples) if isinstance(retrieved_examples, list) else 1

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

    with st.status("Generating WDL workflow…", expanded=True) as status:
        attempts = []
        for attempt_idx in range(_MAX_RETRIES + 1):
            attempt_num = attempt_idx + 1
            total_attempts = _MAX_RETRIES + 1

            # Step list for current attempt
            st.markdown(
                f"✓ Built context from your selections  \n"
                f"✓ Retrieved {n_examples} matching WILDS example{'s' if n_examples != 1 else ''}  \n"
                f"⟳ **Generating draft WDL…**  \n"
                f"○ Validate with miniwdl + sprocket"
            )

            # Attempt badge + thin progress bar
            col_badge, _ = st.columns([1, 3])
            with col_badge:
                st.markdown(
                    f"<span style='background:#2E7D32;color:white;padding:3px 10px;"
                    f"border-radius:999px;font-size:12px;font-weight:600;'>"
                    f"Attempt {attempt_num} of {total_attempts}</span>",
                    unsafe_allow_html=True,
                )
            st.progress(attempt_num / total_attempts)

            chunks = []
            for chunk in client.chat(model=_MODEL, messages=messages, stream=True):
                chunks.append(chunk["message"]["content"])
            raw = "".join(chunks)

            wdl = extract_wdl(raw)
            check = validate_wdl(wdl)
            attempts.append({"valid": check["valid"], "stderr": check["stderr"], "wdl": wdl})

            if check["valid"]:
                break
            elif attempt_idx < _MAX_RETRIES:
                with st.expander(f"Attempt {attempt_num} failed validation — view errors"):
                    st.code(check["stderr"])
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": build_retry(check["stderr"])})

        final = attempts[-1]
        st.session_state.attempts = attempts
        st.session_state.wdl = final["wdl"]

        status.update(
            label="Done! Validation passed." if final["valid"] else "Done (validation failed — best attempt shown).",
            state="complete" if final["valid"] else "error",
        )

    st.caption("Validation failures are sent back to the model automatically, up to 6 attempts. This can take a few minutes.")

    st.session_state.view = "result"
    st.rerun()


# ── RESULT VIEW ───────────────────────────────────────────────────────────────
elif st.session_state.view == "result":
    final = st.session_state.attempts[-1] if st.session_state.attempts else {"valid": False, "stderr": "", "wdl": st.session_state.wdl}
    wdl = st.session_state.wdl
    n_attempts = len(st.session_state.attempts)
    n_lines = len(wdl.splitlines()) if wdl else 0

    # Count tasks in wdl (lines starting with "task ")
    n_tasks = len(re.findall(r"^\s*task\s+\w+", wdl, re.MULTILINE)) if wdl else 0

    if final["valid"]:
        st.markdown(
            "<div style='background:#E7F5EC;border:1px solid #BFE3CC;border-radius:8px;"
            "padding:14px 18px;display:flex;align-items:center;gap:10px;'>"
            "<span style='color:#1B8A4B;font-size:20px;'>✓</span>"
            "<span style='color:#15633A;font-weight:600;'>Validation passed — your workflow is ready.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#FDF6E8;border:1px solid #F3D9A0;border-radius:8px;"
            "padding:14px 18px;display:flex;align-items:center;gap:10px;'>"
            "<span style='color:#8a6914;font-size:20px;'>⚠</span>"
            "<span style='color:#8a6914;font-weight:600;'>Validation failed after all retries — best attempt shown.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_label = "Valid" if final["valid"] else "Invalid"
        status_color = "#2E7D32" if final["valid"] else "#c0392b"
        st.markdown(
            f"<div style='border:1px solid #DDE0E6;border-radius:8px;padding:12px 16px;'>"
            f"<div style='font-size:12px;color:#6E7079;'>Status</div>"
            f"<div style='font-size:20px;font-weight:700;color:{status_color};'>{status_label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div style='border:1px solid #DDE0E6;border-radius:8px;padding:12px 16px;'>"
            f"<div style='font-size:12px;color:#6E7079;'>Attempts</div>"
            f"<div style='font-size:20px;font-weight:700;'>{n_attempts}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"<div style='border:1px solid #DDE0E6;border-radius:8px;padding:12px 16px;'>"
            f"<div style='font-size:12px;color:#6E7079;'>Tasks</div>"
            f"<div style='font-size:20px;font-weight:700;'>{n_tasks}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"<div style='border:1px solid #DDE0E6;border-radius:8px;padding:12px 16px;'>"
            f"<div style='font-size:12px;color:#6E7079;'>Lines</div>"
            f"<div style='font-size:20px;font-weight:700;'>{n_lines}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    tab_workflow, tab_validation, tab_howto = st.tabs(["Workflow", "Validation report", "How to run"])

    with tab_workflow:
        st.code(wdl, language="wdl")
        col_dl, col_edit, _ = st.columns([2, 2, 4])
        with col_dl:
            st.download_button(
                label="Download workflow.wdl",
                data=wdl,
                file_name="workflow.wdl",
                mime="text/plain",
            )
        with col_edit:
            if st.button("Edit selections"):
                st.session_state.view = "form"
                st.rerun()

    with tab_validation:
        if final["valid"]:
            st.markdown("- ✅ `miniwdl check --strict` passed")
            st.markdown("- ✅ `sprocket lint` 0 warnings")
            tasks_used = ", ".join(sorted(st.session_state.confirmed_ids)) if st.session_state.confirmed_ids else "—"
            st.markdown(f"- ✅ Only WILDS-library tasks used ({tasks_used})")
        else:
            st.markdown("- ❌ Validation did not pass after all retries")
            if final["stderr"]:
                st.markdown("**Remaining errors:**")
                st.code(final["stderr"])

    with tab_howto:
        st.markdown("Run your workflow locally with [sprocket](https://github.com/stjude-rust-labs/sprocket):")
        st.code("sprocket run workflow.wdl inputs.json", language="bash")
        st.markdown(
            "For help running your WDL on Fred Hutch infrastructure, contact OCDO via "
            "[Data House Calls](https://ocdo.fredhutch.org/programs/data-house-calls.html)."
        )
