"""Custom CSS/HTML for the WILDS-branded Streamlit UI.

Styling only — no app logic lives here. See the design handoff
(`design_handoff_wdl_writer_ui/README.md`) for the source spec.
"""

STAGE_ORDER = ["form", "approval", "generate", "done"]
STEP_LABELS = ["Describe workflow", "Approve tools", "Generate", "Result"]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

.stApp {
    background: #f6faf7;
}

/* Header */
.wdl-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 8px;
}
.wdl-header img {
    width: 44px;
    height: 44px;
    object-fit: contain;
    border-radius: 8px;
}
.wdl-header-title {
    font-size: 22px;
    font-weight: 700;
    color: #16281f;
    letter-spacing: -0.01em;
    line-height: 1.3;
}
.wdl-header-subtitle {
    font-size: 13px;
    color: #6b8577;
}

/* Step indicator */
.wdl-steps {
    background: #fff;
    border: 1px solid #dfe9e3;
    border-radius: 14px;
    padding: 14px 20px;
    margin: 20px 0 28px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.wdl-step {
    display: flex;
    align-items: center;
    gap: 10px;
}
.wdl-step-circle {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    flex-shrink: 0;
}
.wdl-step-circle.active { background: #2d6a4f; color: #fff; border: 2px solid #2d6a4f; }
.wdl-step-circle.complete { background: #74c69d; color: #16281f; border: 2px solid #2d6a4f; }
.wdl-step-circle.pending { background: #fff; color: #16281f; border: 2px solid #dfe9e3; }
.wdl-step-label { font-size: 14px; }
.wdl-step-label.active { font-weight: 600; color: #16281f; }
.wdl-step-label.complete { font-weight: 500; color: #33473c; }
.wdl-step-label.pending { font-weight: 500; color: #94a89b; }
.wdl-step-line { flex: 0 0 24px; height: 2px; }
.wdl-step-line.complete { background: #74c69d; }
.wdl-step-line.pending { background: #dfe9e3; }

/* Caption / disclaimer card */
.wdl-caption-card {
    background: #fff;
    border: 1px solid #dfe9e3;
    border-radius: 16px;
    padding: 12px 24px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #6b8577;
    line-height: 1.6;
}
.wdl-caption-card strong { color: #33473c; }

/* Question / card containers (Q1-Q5, approve tools, generate, result) */
div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"],
.wdl-card {
    background: #fff;
    border: 1px solid #dfe9e3;
    border-radius: 16px;
    padding: 24px !important;
    margin-bottom: 16px;
}

.wdl-eyebrow {
    font-size: 11px;
    font-weight: 600;
    color: #40916c;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 6px;
    display: flex;
    align-items: baseline;
    gap: 8px;
}
.wdl-eyebrow-optional {
    font-size: 11px;
    font-weight: 400;
    color: #94a89b;
    text-transform: none;
    letter-spacing: normal;
}
.wdl-question {
    font-size: 16px;
    font-weight: 600;
    color: #16281f;
    margin-bottom: 4px;
}

/* Pills / chips for multiselect and st.pills */
span[data-baseweb="tag"] {
    background: #eaf6ef !important;
    border: 1.5px solid #2d6a4f !important;
    border-radius: 999px !important;
    color: #1b4332 !important;
    font-weight: 600 !important;
}
span[data-baseweb="tag"] svg { fill: #1b4332 !important; }

div[data-testid="stMultiSelect"] > div > div {
    border-radius: 10px !important;
    border-color: #dfe9e3 !important;
}

/* st.pills / st.segmented_control pill styling */
div[data-testid="stPills"] label,
div[data-testid="stSegmentedControl"] label {
    border-radius: 999px !important;
    font-weight: 500 !important;
}

/* Buttons */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 10px 26px !important;
}
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"],
.stDownloadButton > button {
    background: #2d6a4f !important;
    border-color: #2d6a4f !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover,
.stDownloadButton > button:hover {
    background: #1b4332 !important;
    border-color: #1b4332 !important;
}
.stButton > button[kind="secondary"] {
    background: #fff !important;
    border: 1.5px solid #dfe9e3 !important;
    color: #33473c !important;
}

/* Tool approval rows: bordered containers nested one level inside the
   "Approve tools" card, identified by containing a checkbox. */
div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stCheckbox"]) {
    border-radius: 10px !important;
    background: #f6faf7 !important;
    border: 1px solid #dfe9e3 !important;
    padding: 6px 12px !important;
    margin-bottom: 10px !important;
}
div[data-testid="stCheckbox"] label p {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #16281f;
}
.wdl-tool-count { font-size: 12px; color: #94a89b; }
div[data-testid="stCheckbox"] span[data-baseweb="checkbox"] > div:first-child {
    border-radius: 6px !important;
}

/* Code / terminal panel */
div[data-testid="stCode"] {
    background: #16281f !important;
    border-radius: 12px !important;
}
div[data-testid="stCode"] pre {
    background: transparent !important;
}
div[data-testid="stCode"] code {
    color: #d7f0e2 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}
div[data-testid="stCode"] code span {
    color: inherit !important;
}

/* Status / success banners */
div[data-testid="stStatus"] {
    border-radius: 12px !important;
    border-color: #dfe9e3 !important;
}
.wdl-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #eaf6ef;
    color: #1b4332;
    border: 1px solid #bfe3cf;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 999px;
}
div[data-testid="stAlertContentSuccess"],
div[data-testid="stAlertContainer"]:has(div[data-testid="stAlertContentSuccess"]) {
    background: #eaf6ef !important;
    border: 1px solid #bfe3cf !important;
    color: #1b4332 !important;
    border-radius: 10px !important;
}

.wdl-card-title {
    font-size: 18px;
    font-weight: 700;
    color: #16281f;
}
.wdl-card-desc {
    font-size: 14px;
    color: #6b8577;
    line-height: 1.6;
    margin-bottom: 4px;
}
.wdl-card-desc strong { color: #33473c; }

.wdl-footer {
    font-size: 13px;
    color: #6b8577;
    border-top: 1px solid #f0f4f1;
    padding-top: 16px;
    margin-top: 4px;
}
.wdl-footer a { color: #2d6a4f; font-weight: 600; }
</style>
"""


def inject_base_css():
    """Injects the global stylesheet. Call once near the top of the app."""
    import streamlit as st

    st.markdown(_CSS, unsafe_allow_html=True)


def render_header(logo_path: str):
    import base64
    import streamlit as st

    with open(logo_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <div class="wdl-header">
            <img src="data:image/jpeg;base64,{encoded}" alt="WILDS logo">
            <div>
                <div class="wdl-header-title">WILDS WDL Writer</div>
                <div class="wdl-header-subtitle">Generate validated WDL workflows from the WILDS WDL Library</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_indicator(current_stage: str):
    import streamlit as st

    current_idx = STAGE_ORDER.index(current_stage)

    parts = ['<div class="wdl-steps">']
    for i, label in enumerate(STEP_LABELS):
        if i > 0:
            line_state = "complete" if i <= current_idx else "pending"
            parts.append(f'<div class="wdl-step-line {line_state}"></div>')

        if i < current_idx:
            circle_state, label_state, num = "complete", "complete", "✓"
        elif i == current_idx:
            circle_state, label_state, num = "active", "active", str(i + 1)
        else:
            circle_state, label_state, num = "pending", "pending", str(i + 1)

        parts.append(
            f'<div class="wdl-step">'
            f'<div class="wdl-step-circle {circle_state}">{num}</div>'
            f'<div class="wdl-step-label {label_state}">{label}</div>'
            f"</div>"
        )
    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)


def render_caption_card(html: str):
    import streamlit as st

    st.markdown(f'<div class="wdl-caption-card">{html}</div>', unsafe_allow_html=True)


def render_eyebrow(label: str, optional: bool = False):
    import streamlit as st

    optional_html = '<span class="wdl-eyebrow-optional">optional</span>' if optional else ""
    st.markdown(f'<div class="wdl-eyebrow">{label}{optional_html}</div>', unsafe_allow_html=True)


def render_question(text: str):
    import streamlit as st

    st.markdown(f'<div class="wdl-question">{text}</div>', unsafe_allow_html=True)


def render_tool_checkbox(name: str, task_count: int, key: str) -> bool:
    """Renders one tool-approval row as a real st.checkbox, styled to match
    the mockup's row look. Returns the checkbox's current (checked) value."""
    import streamlit as st

    with st.container(border=True):
        check_col, count_col = st.columns([8, 1])
        with check_col:
            checked = st.checkbox(name, value=True, key=key)
        with count_col:
            st.markdown(
                f'<div class="wdl-tool-count" style="text-align:right; padding-top:8px;">{task_count} task(s)</div>',
                unsafe_allow_html=True,
            )
    return checked
