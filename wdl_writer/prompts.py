"""Prompt assembly for WDL generation.

Production path: `build_system()` and `build_user()` compose the layers
(WDL spec, optional minimal example, optional RAG-retrieved examples,
optional tool constraints) into the messages sent to the LLM.

Benchmarking path: `PROMPT_CONFIGS` names ablation tiers — each entry is
a kwargs dict for `build_system()` — so the benchmark can measure the
contribution of each layer independently.
"""

from __future__ import annotations
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_SPEC = (_PROMPTS_DIR / "system_spec.md").read_text()
_EXAMPLE = (_PROMPTS_DIR / "system_example.md").read_text()
_WILDS = (_PROMPTS_DIR / "system_wilds.md").read_text()
_USER_TEMPLATE = (_PROMPTS_DIR / "user_template.md").read_text()
_RETRY = (_PROMPTS_DIR / "retry_prompt.md").read_text()
_SHORT_SYSTEM = (_PROMPTS_DIR / "short_system_prompt.md").read_text()
_SHORT_EXAMPLE = (_PROMPTS_DIR / "short_example.md").read_text()
_SHORT_USER_TEMPLATE = (_PROMPTS_DIR / "short_user_template.md").read_text()
_SELECT_SYSTEM = (_PROMPTS_DIR / "select_system_prompt.md").read_text()
_SELECT_EXAMPLE = (_PROMPTS_DIR / "select_example.md").read_text()

# Bare-bones system prompt used by the "raw" benchmarking tier — no WDL
# context at all, just a code-fence instruction. Kept inline because it's
# the baseline, not a real production prompt.
_RAW_SYSTEM = (
    "You are an expert programmer. "
    "Respond only with valid code inside a ```wdl code block."
)


def build_system(
    include_spec: bool = True,
    include_example: bool = False,
    include_wilds: bool = False,
    retrieved_examples: list[str] | None = None,
) -> str:
    """Assemble the system prompt from its component layers."""
    if not include_spec:
        return _RAW_SYSTEM

    parts = [_SPEC]
    if include_example:
        parts.append(_EXAMPLE)
    if include_wilds:
        parts.append(_WILDS)
    if retrieved_examples:
        parts.append("RETRIEVED TASK METADATA (candidate tasks for this workflow):\n\n"
                     + "\n\n---\n\n".join(retrieved_examples))
    return "\n\n".join(parts)


def build_user(template_vars: dict[str, str]) -> str:
    """Render the fill-in-the-blank user template with the given values."""
    result = _USER_TEMPLATE
    for key, value in template_vars.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def build_short_system() -> str:
    """Return the short system prompt with its worked example appended."""
    return _SHORT_SYSTEM + "\n\n" + _SHORT_EXAMPLE


def build_select_system() -> str:
    """Return the task-selection system prompt with its worked example appended.

    Used for the first of two LLM calls in the short pipeline: this one picks
    which candidate tasks to chain together (no WDL syntax involved), and its
    output narrows the candidate list for the second call built by
    build_short_system()/build_short_user().
    """
    return _SELECT_SYSTEM + "\n\n" + _SELECT_EXAMPLE


def build_short_user(template_vars: dict[str, str]) -> str:
    """Render the short fill-in-the-blank user template with the given values."""
    result = _SHORT_USER_TEMPLATE
    for key, value in template_vars.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def build_retry(stderr: str) -> str:
    """Render the retry prompt with the validator's error output."""
    return _RETRY.replace("{{stderr}}", stderr)


# Ablation tiers for benchmarking. Each value is kwargs for build_system(),
# optionally with a `use_rag: True` flag indicating that the caller should
# retrieve module tasks from the docstore and pass them as `retrieved_examples`.
PROMPT_CONFIGS = {
    "raw": {"include_spec": False},
    "spec": {"include_spec": True, "include_example": False},
    "spec_plus_example": {"include_spec": True, "include_example": True},
    "spec_plus_wilds": {"include_spec": True, "include_wilds": True},
    "full": {"include_spec": True, "include_example": True, "include_wilds": True},
    "full_plus_rag": {"include_spec": True, "include_example": True, "include_wilds": True, "use_rag": True},
}
