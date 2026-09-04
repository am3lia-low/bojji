"""Three-stage officer workspace for citizen correspondence.

Run with::

    streamlit run app/streamlit_app.py

The interface deliberately separates opening an inbox from running the expensive
classifier. Source messages are always read-only; only generated drafts can be
edited. Processing results live in ``st.session_state`` so selecting a message or
editing a draft never repeats inference or an external drafting call.
"""

from __future__ import annotations

import html
import json
import sys
import time
from pathlib import Path
from typing import Any, Literal, cast

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import Labelled, split  # noqa: E402

from triage.schemas import (  # noqa: E402
    Action,
    DraftResult,
    DraftStatus,
    ScrubRecord,
    TriageState,
)

RESULTS = ROOT / "eval" / "results"
DEMO_INBOX = ROOT / "data" / "demo_inbox.json"
DEMO_INBOX_VERSION = 4
DEFAULT_SPLIT = "test"
DEFAULT_LIMIT = 20
DEFAULT_MULTIPLIER = 1.0
PROCESSING_BATCH_SIZE = 8

Stage = Literal["inbox", "processing", "results"]

st.set_page_config(
    page_title="Citizen correspondence — triage workspace",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_APP_CSS = """
<style>
:root {
    --workspace-blue: #2563eb;
    --workspace-blue-soft: rgba(37, 99, 235, 0.11);
    --workspace-border: rgba(128, 128, 128, 0.22);
    --outlook-font: "Aptos", "Segoe UI", Calibri, Arial, sans-serif;
}

/* This workflow has no secondary control surface. */
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
div.block-container { max-width: 1500px; padding-top: 1.65rem; padding-bottom: 3rem; }
header[data-testid="stHeader"] { background: transparent; }

/* A radio group gives the list true single-row semantics. Its circular selector
   is hidden because the selected-row tint is the affordance, as in Outlook. */
div[class*="st-key-inbox-message-list"] div[role="radiogroup"],
div[class*="st-key-result-message-list"] div[role="radiogroup"] {
    border: 1px solid var(--workspace-border);
    border-radius: 10px;
    max-height: 615px;
    overflow-y: auto;
    gap: 0;
    font-family: var(--outlook-font);
}
div[class*="st-key-inbox-message-list"] label[data-baseweb="radio"],
div[class*="st-key-result-message-list"] label[data-baseweb="radio"] {
    width: 100%;
    margin: 0;
    padding: 9px 12px;
    border-bottom: 1px solid var(--workspace-border);
    align-items: flex-start;
    font-family: var(--outlook-font);
}
div[class*="st-key-inbox-message-list"] label[data-baseweb="radio"]:last-child,
div[class*="st-key-result-message-list"] label[data-baseweb="radio"]:last-child {
    border-bottom: 0;
}
div[class*="st-key-inbox-message-list"] label[data-baseweb="radio"] > div:first-child,
div[class*="st-key-result-message-list"] label[data-baseweb="radio"] > div:first-child {
    display: none;
}
div[class*="st-key-inbox-message-list"] label[data-baseweb="radio"]:hover,
div[class*="st-key-result-message-list"] label[data-baseweb="radio"]:hover {
    background: rgba(128, 128, 128, 0.09);
}
div[class*="st-key-inbox-message-list"] label[data-baseweb="radio"]:has(input:checked),
div[class*="st-key-result-message-list"] label[data-baseweb="radio"]:has(input:checked) {
    background: var(--workspace-blue-soft);
    box-shadow: inset 3px 0 0 var(--workspace-blue);
}
div[class*="st-key-inbox-message-list"] label p,
div[class*="st-key-result-message-list"] label p {
    font-family: var(--outlook-font);
    font-size: 0.9rem;
    font-weight: 650;
    line-height: 1.25;
}
div[class*="st-key-inbox-message-list"] label small,
div[class*="st-key-result-message-list"] label small {
    font-family: var(--outlook-font);
    font-size: 0.76rem;
    line-height: 1.3;
    opacity: 0.72;
}

/* The stage marker is navigational context rather than a second toolbar. */
.workflow-steps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin: 0.3rem 0 1.45rem;
}
.workflow-step {
    padding: 9px 12px;
    border-bottom: 3px solid var(--workspace-border);
    color: rgba(128, 128, 128, 0.9);
    font-size: 0.78rem;
    font-weight: 650;
}
.workflow-step.active { border-color: var(--workspace-blue); color: var(--workspace-blue); }
.workflow-step.done { border-color: #16a34a; color: inherit; }
.workflow-number {
    display: inline-flex;
    width: 1.35rem;
    height: 1.35rem;
    border-radius: 50%;
    align-items: center;
    justify-content: center;
    margin-right: 0.4rem;
    background: rgba(128, 128, 128, 0.13);
}
.workflow-step.active .workflow-number { background: var(--workspace-blue); color: white; }
.workflow-step.done .workflow-number { background: #16a34a; color: white; }

div[data-testid="stMetric"] {
    border: 1px solid var(--workspace-border);
    border-radius: 10px;
    padding: 11px 14px;
}
div[data-testid="stMetricValue"] { font-size: 1.5rem !important; }
div[data-testid="stMetricLabel"] { font-size: 0.76rem !important; opacity: 0.75; }

.mail-pane {
    border: 1px solid var(--workspace-border);
    border-radius: 10px;
    padding: 18px 20px;
    min-height: 230px;
    font-family: var(--outlook-font);
}
.mail-body {
    white-space: pre-wrap;
    line-height: 1.5;
    font-family: var(--outlook-font);
    font-size: 11pt;
}
.mail-subject {
    font-family: var(--outlook-font);
    font-size: 1.38rem;
    font-weight: 680;
    line-height: 1.3;
}
.mail-meta {
    color: #737983;
    font-family: var(--outlook-font);
    font-size: 0.8rem;
    margin: 3px 0 18px;
}

.processing-list {
    border: 1px solid var(--workspace-border);
    border-radius: 10px;
    height: 430px;
    overflow-y: auto;
    background: rgba(128, 128, 128, 0.025);
}
.processing-row {
    padding: 9px 12px;
    border-bottom: 1px solid var(--workspace-border);
    font-family: var(--outlook-font);
    line-height: 1.35;
}
.processing-row:last-child { border-bottom: 0; }
.processing-subject { font-size: 0.83rem; font-weight: 650; }
.processing-meta { font-size: 0.72rem; opacity: 0.68; margin-top: 2px; }
.empty-list { padding: 34px 16px; text-align: center; opacity: 0.6; }

/* The original email should look readable, not like a disabled form control. */
.readonly-note { opacity: 0.67; font-size: 0.78rem; }

/* Generated reply text uses the same typography as an Outlook compose window. */
div[class*="st-key-draft-text-"] textarea {
    font-family: var(--outlook-font) !important;
    font-size: 11pt !important;
    line-height: 1.5 !important;
}

@media (max-width: 900px) {
    .workflow-steps { grid-template-columns: 1fr; }
    .processing-list { height: 280px; }
}
</style>
"""
st.markdown(_APP_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Lightweight inbox loading and deferred processing resources
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner=False)
def _mailbox(split_name: str, limit: int) -> tuple[Labelled, ...]:
    """Load the fixed, outcome-balanced synthetic demonstration inbox.

    The manifest was selected offline using the frozen model and configured safety
    policy. It is a capability showcase, not an estimate of production mail volume.
    Runtime classification still receives only each email; no stored outcome or
    ground-truth label is supplied to the classifier or router.
    """
    rows = split(split_name)
    if split_name == DEFAULT_SPLIT and DEMO_INBOX.exists():
        payload = json.loads(DEMO_INBOX.read_text(encoding="utf-8"))
        ids = payload.get("email_ids", [])
        by_id = {item.email.id: item for item in rows}
        selected = [by_id[email_id] for email_id in ids if email_id in by_id]
        if len(selected) >= min(limit, len(rows)):
            return tuple(selected[:limit])

    # A missing or stale manifest must leave the demo usable, even if less balanced.
    return tuple(sorted(rows, key=lambda item: item.email.received_at, reverse=True)[:limit])


@st.cache_resource(show_spinner=False)
def _index() -> Any:
    from triage.sop.index import build_index

    return build_index()


@st.cache_resource(show_spinner=False)
def _scrubber() -> Any:
    from triage.pii.scrubber import Scrubber

    return Scrubber()


@st.cache_resource(show_spinner=False)
def _classifier() -> Any:
    # Importing the runtime and materialising its 90 MB weights both happen only
    # after the officer explicitly starts processing.
    from triage.models.encoder import EncoderClassifier

    return EncoderClassifier()


@st.cache_resource(show_spinner=False)
def _draft_client() -> Any | None:
    from triage.llm.client import GeminiClient, LLMError

    try:
        return GeminiClient()
    except LLMError:
        return None


@st.cache_data(show_spinner=False)
def _classify_chunk(
    split_name: str,
    limit: int,
    start: int,
    stop: int,
    multiplier: float,
    selection_version: int,
) -> list[TriageState]:
    """Run a real batched classification and routing step, cached by chunk."""
    from triage.models.calibration import TemperatureScaler
    from triage.nodes.calibrate import calibrate, rollup
    from triage.nodes.flags import detect_flags
    from triage.nodes.route import load_thresholds, route

    if selection_version != DEMO_INBOX_VERSION:
        raise ValueError(f"unsupported demo inbox version {selection_version}")
    items = _mailbox(split_name, limit)[start:stop]
    index = _index()
    scrubber = _scrubber()
    classifier = _classifier()
    scaler = TemperatureScaler.load()
    thresholds = load_thresholds()
    bucket_of = dict(index.bucket)

    scrubs = [scrubber.scrub(item.email.text) for item in items]
    classifications = classifier.predict_batch([scrub.text for scrub in scrubs])

    states: list[TriageState] = []
    for item, scrub, classification in zip(items, scrubs, classifications, strict=True):
        bucket, summed = rollup(classification, bucket_of)
        score = calibrate(bucket, summed, scaler)
        flags = detect_flags(scrub.text, classification)
        sops = index.sops_for(classification.label)
        decision = route(
            score,
            sops,
            flags,
            dict(thresholds),
            calibrated=scaler.fitted,
            multiplier=multiplier,
        )
        draft = None
        if not decision.is_automated:
            draft = DraftResult(
                status=DraftStatus.NOT_ATTEMPTED,
                sop_ids=tuple(sop.sop_id for sop in sops),
            )
        states.append(
            TriageState(
                email=item.email,
                scrub=ScrubRecord(
                    text=scrub.text,
                    vault=scrub.vault,
                    counts=scrub.counts,
                ),
                classification=classification,
                bucket_score=score,
                sop_ids=tuple(sop.sop_id for sop in sops),
                decision=decision,
                draft=draft,
            )
        )
    return states


def _generate_draft(state: TriageState) -> TriageState:
    """Finish one already-classified state without running the encoder twice."""
    from triage.nodes.draft import draft_node

    update = draft_node(state, _index(), _draft_client())
    return state.model_copy(update=update)


@st.cache_data(show_spinner=False)
def _risk_coverage() -> dict[str, Any] | None:
    path = RESULTS / "risk_coverage.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object in {path}")
    return cast(dict[str, Any], payload)


# --------------------------------------------------------------------------- #
# Session workflow and shared presentation helpers
# --------------------------------------------------------------------------- #


def _stage() -> Stage:
    if "workflow_stage" not in st.session_state:
        st.session_state["workflow_stage"] = "inbox"
    value = st.session_state["workflow_stage"]
    return cast(Stage, value if value in ("inbox", "processing", "results") else "inbox")


def _begin_processing() -> None:
    st.session_state["workflow_stage"] = "processing"
    st.session_state["processed_states"] = []
    st.session_state["processing_error"] = None
    st.session_state.pop("result_selected", None)
    st.session_state.pop("result_filter", None)
    st.session_state.pop("saved_drafts", None)
    for key in list(st.session_state):
        if str(key).startswith("draft-text-"):
            st.session_state.pop(key, None)


def _reset_workflow() -> None:
    st.session_state["workflow_stage"] = "inbox"
    st.session_state["processed_states"] = []
    st.session_state["processing_error"] = None
    st.session_state.pop("result_selected", None)
    st.session_state.pop("result_filter", None)


def _render_stage_bar(active: Stage) -> None:
    stages: tuple[tuple[Stage, str], ...] = (
        ("inbox", "Inbox loaded"),
        ("processing", "Processing"),
        ("results", "Results"),
    )
    active_index = next(i for i, (name, _) in enumerate(stages) if name == active)
    cells: list[str] = []
    for index, (_, label) in enumerate(stages):
        state_class = "active" if index == active_index else "done" if index < active_index else ""
        marker = "✓" if index < active_index else str(index + 1)
        cells.append(
            f'<div class="workflow-step {state_class}">'
            f'<span class="workflow-number">{marker}</span>{label}</div>'
        )
    st.markdown(
        f'<div class="workflow-steps">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def _pretty(value: Any) -> str:
    return str(value).replace("_", " ").replace(":", " ·").strip()


def _email_heading(email: Any) -> None:
    subject = html.escape(email.subject or "(no subject)", quote=True)
    sender = html.escape(email.sender or "unknown sender", quote=True)
    st.markdown(
        f"<div class='mail-subject'>{subject}</div>"
        f"<div class='mail-meta'>{sender} · "
        f"{email.received_at.strftime('%d %b %Y, %H:%M')}</div>",
        unsafe_allow_html=True,
    )


def _read_only_email(email: Any) -> None:
    body = html.escape(email.body, quote=True)
    st.markdown(
        f'<div class="mail-pane"><div class="mail-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def _reason_text(state: TriageState) -> str:
    decision = state.decision
    if state.draft_failed and state.draft is not None and state.draft.failure_reason is not None:
        return f"Draft failed · {_pretty(state.draft.failure_reason)}"
    if decision is None or decision.reason is None:
        return "Needs officer review"
    if str(decision.reason) == "low_confidence":
        return f"Low confidence · {decision.confidence:.2f} below {decision.threshold:.2f}"
    return _pretty(decision.reason).capitalize()


def _state_status(state: TriageState) -> tuple[str, str]:
    decision = state.decision
    if state.draft_failed:
        return _reason_text(state), "red"
    if state.in_human_queue:
        return _reason_text(state), "orange"
    if state.draft is not None and state.draft.status is DraftStatus.OK:
        if decision is not None and decision.action is Action.REDIRECT:
            return "Redirect draft ready", "violet"
        return "Draft ready", "green"
    if decision is not None and decision.action is Action.REDIRECT:
        return "Redirect", "violet"
    return "Processed", "blue"


# --------------------------------------------------------------------------- #
# Stage 1: read-only inbox
# --------------------------------------------------------------------------- #


def _inbox_list(items: list[Labelled]) -> None:
    if not items:
        return
    by_id = {item.email.id: item for item in items}
    st.radio(
        "Inbox messages",
        options=list(by_id),
        format_func=lambda email_id: by_id[email_id].email.subject or "(no subject)",
        captions=[
            f"New · {item.email.sender or 'unknown sender'} · "
            f"{item.email.received_at.strftime('%d %b, %H:%M')}"
            for item in items
        ],
        key="inbox_selected",
        label_visibility="collapsed",
    )


def _render_inbox(items: tuple[Labelled, ...]) -> None:
    title_col, action_col = st.columns([4.4, 1.25], vertical_alignment="bottom")
    with title_col:
        st.caption("OFFICER WORKSPACE")
        st.title("Citizen correspondence")
        st.caption(
            "An outcome-balanced synthetic demonstration inbox. Select a message to read it "
            "before triage."
        )
    with action_col:
        st.button(
            f"Process {len(items)} emails",
            type="primary",
            use_container_width=True,
            on_click=_begin_processing,
        )
        st.caption("Eligible routes are drafted live when a Gemini key is configured.")

    _render_stage_bar("inbox")

    dates = [item.email.received_at for item in items]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Awaiting triage", len(items))
    metric_cols[1].metric("Unresolved", len(items))
    metric_cols[2].metric("Oldest received", min(dates).strftime("%d %b") if dates else "—")
    metric_cols[3].metric("Queue status", "Ready")

    st.markdown("<br>", unsafe_allow_html=True)
    list_col, detail_col = st.columns([1, 1.55], gap="large")

    email_ids = {item.email.id for item in items}
    if st.session_state.get("inbox_selected") not in email_ids:
        st.session_state["inbox_selected"] = items[0].email.id if items else None

    with list_col:
        st.subheader("Inbox")
        st.caption(f"{len(items)} messages · newest first")
        if not items:
            st.info("There are no emails in this inbox.")
        _inbox_list(list(items))

    with detail_col:
        selected_id = st.session_state.get("inbox_selected")
        selected = next((item for item in items if item.email.id == selected_id), None)
        if selected is None:
            st.info("Select an email to open it.")
            return
        _email_heading(selected.email)
        st.markdown(
            '<div class="readonly-note">Received message · read-only</div>',
            unsafe_allow_html=True,
        )
        _read_only_email(selected.email)
        st.caption(
            "The source message cannot be changed. Personal data is scrubbed locally before "
            "classification or any external drafting call."
        )


# --------------------------------------------------------------------------- #
# Stage 2: live batch processing
# --------------------------------------------------------------------------- #


def _processing_list(
    items: tuple[Labelled, ...],
    states_by_id: dict[str, TriageState] | None = None,
) -> str:
    if not items:
        return '<div class="processing-list"><div class="empty-list">No messages</div></div>'

    rows: list[str] = []
    state_map = states_by_id or {}
    for item in items:
        email = item.email
        state = state_map.get(email.id)
        if state is None:
            status = "Waiting"
        else:
            label = state.classification.label if state.classification is not None else "Processed"
            status_text, _ = _state_status(state)
            status = f"{_pretty(label)} · {status_text}"
        rows.append(
            '<div class="processing-row">'
            f'<div class="processing-subject">{html.escape(email.subject or "(no subject)")}</div>'
            f'<div class="processing-meta">{html.escape(email.sender or "unknown sender")} · '
            f'{html.escape(status)}</div></div>'
        )
    return f'<div class="processing-list">{"".join(rows)}</div>'


def _render_processing(items: tuple[Labelled, ...]) -> None:
    title_col, action_col = st.columns([4.4, 1.25], vertical_alignment="bottom")
    with title_col:
        st.caption("OFFICER WORKSPACE")
        st.title("Processing correspondence")
        st.caption("Messages are scrubbed, classified, routed, and drafted where permitted.")
    with action_col:
        st.button("Return to inbox", use_container_width=True, on_click=_reset_workflow)

    _render_stage_bar("processing")

    states: list[TriageState] = list(st.session_state.get("processed_states", []))
    progress_bar = st.progress(0, text="Preparing the local classifier…")
    count_slot = st.empty()
    outstanding_col, processed_col = st.columns(2, gap="large")
    with outstanding_col:
        st.subheader("Outstanding")
        outstanding_slot = st.empty()
    with processed_col:
        st.subheader("Processed")
        processed_slot = st.empty()

    def repaint(message: str, progress: float) -> None:
        state_map = {state.email.id: state for state in states}
        pending = tuple(item for item in items if item.email.id not in state_map)
        completed = tuple(item for item in items if item.email.id in state_map)
        outstanding_slot.markdown(_processing_list(pending), unsafe_allow_html=True)
        processed_slot.markdown(_processing_list(completed, state_map), unsafe_allow_html=True)
        progress_bar.progress(min(100, max(0, int(progress * 100))), text=message)
        count_slot.caption(f"{len(states)} of {len(items)} messages classified")

    repaint("Preparing the local classifier…", 0.0)

    try:
        while len(states) < len(items):
            start = len(states)
            stop = min(start + PROCESSING_BATCH_SIZE, len(items))
            progress_bar.progress(
                int(75 * start / max(len(items), 1)),
                text=f"Classifying messages {start + 1}–{stop} of {len(items)}…",
            )
            states.extend(
                _classify_chunk(
                    DEFAULT_SPLIT,
                    DEFAULT_LIMIT,
                    start,
                    stop,
                    DEFAULT_MULTIPLIER,
                    DEMO_INBOX_VERSION,
                )
            )
            st.session_state["processed_states"] = states
            repaint(
                f"Classified {stop} of {len(items)} messages",
                0.75 * stop / max(len(items), 1),
            )
            # Cached chunks can otherwise move so quickly that the transition is
            # imperceptible. This is short enough not to become artificial load.
            time.sleep(0.06)

        draft_indexes = [
            index
            for index, state in enumerate(states)
            if state.decision is not None and state.decision.is_automated and state.draft is None
        ]
        draft_total = len(draft_indexes)
        for draft_number, state_index in enumerate(draft_indexes, start=1):
            state = states[state_index]
            progress_bar.progress(
                int(75 + 25 * (draft_number - 1) / max(draft_total, 1)),
                text=f"Generating grounded draft {draft_number} of {draft_total}…",
            )
            states[state_index] = _generate_draft(state)
            st.session_state["processed_states"] = states
            repaint(
                f"Generated {draft_number} of {draft_total} eligible drafts",
                0.75 + 0.25 * draft_number / max(draft_total, 1),
            )

    except Exception as exc:  # noqa: BLE001 -- the UI must remain recoverable
        st.session_state["processing_error"] = f"{type(exc).__name__}: {exc}"
        progress_bar.progress(
            int(75 * len(states) / max(len(items), 1)),
            text="Processing stopped",
        )
        st.error(f"Processing stopped: {type(exc).__name__}: {exc}")
        retry_col, back_col = st.columns([1, 1])
        if retry_col.button("Retry from here", type="primary", use_container_width=True):
            st.session_state["processing_error"] = None
            st.rerun()
        back_col.button("Back to inbox", use_container_width=True, on_click=_reset_workflow)
        return

    progress_bar.progress(100, text="Processing complete")
    st.session_state["processing_error"] = None
    st.session_state["workflow_stage"] = "results"
    if states and not st.session_state.get("result_selected"):
        st.session_state["result_selected"] = states[0].email.id
    time.sleep(0.3)
    st.rerun()


# --------------------------------------------------------------------------- #
# Stage 3: routed queue and editable drafts
# --------------------------------------------------------------------------- #


def _result_list(states: list[TriageState]) -> None:
    if not states:
        return
    by_id = {state.email.id: state for state in states}
    captions: list[str] = []
    for state in states:
        status, colour = _state_status(state)
        marker = {"red": "⛔", "orange": "⚠", "green": "✓", "violet": "↗"}.get(
            colour, "●"
        )
        predicted = state.classification.label if state.classification is not None else "unknown"
        captions.append(
            f"{marker} {status} · {_pretty(predicted)} · "
            f"{state.email.sender or 'unknown sender'} · "
            f"{state.email.received_at.strftime('%d %b')}"
        )
    st.radio(
        "Processed messages",
        options=list(by_id),
        format_func=lambda email_id: by_id[email_id].email.subject or "(no subject)",
        captions=captions,
        key="result_selected",
        label_visibility="collapsed",
    )


def _matches_filter(state: TriageState, selected_filter: str) -> bool:
    if selected_filter == "Officer queue":
        return state.in_human_queue
    if selected_filter == "Drafted":
        return state.draft is not None and state.draft.status is DraftStatus.OK
    if selected_filter == "Draft failures":
        return state.draft_failed
    if selected_filter == "Redirects":
        return state.decision is not None and state.decision.action is Action.REDIRECT
    return True


def _replace_state(updated: TriageState) -> None:
    states: list[TriageState] = list(st.session_state.get("processed_states", []))
    st.session_state["processed_states"] = [
        updated if state.email.id == updated.email.id else state for state in states
    ]


def _render_draft(state: TriageState) -> None:
    draft = state.draft
    if draft is None or draft.status is DraftStatus.NOT_ATTEMPTED:
        st.info(
            "No automatic draft was generated because this message requires "
            "an officer decision."
        )
        return

    if draft.status is DraftStatus.FAILED:
        reason = _pretty(draft.failure_reason or "unknown")
        st.error(f"A draft could not be generated: {reason}.")
        st.caption(
            "The routing decision is retained, but the item remains in the attention queue. "
            "Its supporting procedure is available below."
        )
        if st.button("Retry draft", key=f"retry-draft-{state.email.id}", type="primary"):
            with st.spinner("Generating a new grounded draft…"):
                updated = _generate_draft(state.model_copy(update={"draft": None}))
                _replace_state(updated)
            st.rerun()
        return

    st.subheader("Draft reply")
    st.caption("Editable working copy · nothing is sent from this demo")
    widget_key = f"draft-text-{state.email.id}"
    edited = st.text_area(
        "Reply text",
        value=draft.text or "",
        height=260,
        key=widget_key,
        label_visibility="collapsed",
    )
    saved_drafts: dict[str, str] = st.session_state.setdefault("saved_drafts", {})
    save_col, reset_col, status_col = st.columns([1, 1, 2.2], vertical_alignment="center")
    if save_col.button("Save changes", key=f"save-draft-{state.email.id}", type="primary"):
        saved_drafts[state.email.id] = edited
        st.toast("Draft saved in this session", icon="✅")
    if reset_col.button("Reset draft", key=f"reset-draft-{state.email.id}"):
        st.session_state[widget_key] = draft.text or ""
        saved_drafts.pop(state.email.id, None)
        st.rerun()
    baseline = saved_drafts.get(state.email.id, draft.text or "")
    if edited != baseline:
        status_col.caption("Unsaved changes")
    elif state.email.id in saved_drafts:
        status_col.caption("Saved in this browser session")
    else:
        status_col.caption(
            f"Grounded on {', '.join(draft.grounded_on) or 'supporting procedure'}"
        )


def _render_procedure(state: TriageState) -> None:
    st.divider()
    if not state.sop_ids:
        st.error(
            "No supporting procedure is indexed for this class. The message was escalated "
            "rather than answered without evidence."
        )
        return
    index = _index()
    st.markdown(f"**Supporting procedure · {', '.join(state.sop_ids)}**")
    for sop_id in state.sop_ids:
        sop = index.by_id.get(sop_id)
        if sop is None:
            continue
        with st.expander(
            f"{sop.sop_id} — {sop.title}",
            expanded=len(state.sop_ids) == 1,
        ):
            st.markdown(sop.body)


def _render_risk_coverage() -> None:
    st.divider()
    show_curve = st.toggle("Show risk and coverage analysis", value=False)
    if not show_curve:
        return
    curve = _risk_coverage()
    if curve is None:
        st.caption("Run `python eval/run_eval.py` to produce the risk-coverage curve.")
        return
    st.subheader("Risk vs coverage")
    st.caption(
        "Swept with the real router over a global threshold multiplier and reported per topic."
    )
    try:
        import pandas as pd

        frame = (
            pd.DataFrame(curve["overall"])[["coverage", "risk"]]
            .groupby("coverage", as_index=True)
            .mean()
            .sort_index()
        )
        st.line_chart(frame)
        point = min(
            curve["overall"],
            key=lambda value: abs(value["multiplier"] - DEFAULT_MULTIPLIER),
        )
        st.caption(
            f"Configured point — coverage {point['coverage']:.1%}, risk {point['risk']:.1%} "
            f"over {point['n']} emails. AURC {curve.get('aurc_overall')}"
        )
    except ImportError:
        st.caption("pandas is needed for the chart.")


def _render_results(states: list[TriageState]) -> None:
    title_col, action_col = st.columns([4.4, 1.25], vertical_alignment="bottom")
    with title_col:
        st.caption("OFFICER WORKSPACE")
        st.title("Triage results")
        st.caption(
            "Review escalations and edit grounded response drafts before any action is taken."
        )
    with action_col:
        st.button("Start over", use_container_width=True, on_click=_reset_workflow)

    _render_stage_bar("results")

    officer_queue = sum(state.in_human_queue for state in states)
    policy_escalations = sum(
        state.decision is None or not state.decision.is_automated for state in states
    )
    draft_failures = sum(state.draft_failed for state in states)
    auto_replies = sum(
        state.decision is not None and state.decision.action is Action.AUTO_REPLY
        for state in states
    )
    drafted = sum(
        state.draft is not None and state.draft.status is DraftStatus.OK for state in states
    )
    redirects = sum(
        state.decision is not None and state.decision.action is Action.REDIRECT for state in states
    )
    automated = sum(
        state.decision is not None and state.decision.is_automated for state in states
    )
    metric_cols = st.columns(6)
    metric_cols[0].metric("Officer queue", officer_queue)
    metric_cols[1].metric("Policy escalations", policy_escalations)
    metric_cols[2].metric("Draft failures", draft_failures)
    metric_cols[3].metric("Drafts ready", drafted)
    metric_cols[4].metric(
        "Automated routes",
        automated,
        help=f"{auto_replies} auto-replies and {redirects} redirects selected by the router.",
    )
    metric_cols[5].metric("Routing coverage", f"{automated / max(len(states), 1):.1%}")

    if draft_failures:
        failure_reasons: dict[str, int] = {}
        for state in states:
            if state.draft_failed and state.draft is not None:
                reason = _pretty(state.draft.failure_reason or "unknown")
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        breakdown = " · ".join(
            f"{reason}: {count}" for reason, count in sorted(failure_reasons.items())
        )
        st.warning(
            f"{draft_failures} automated route{'s' if draft_failures != 1 else ''} could not "
            f"be drafted ({breakdown}). They remain in the officer queue; the routing "
            "decisions are unchanged."
        )

    st.markdown("<br>", unsafe_allow_html=True)
    queue_col, detail_col = st.columns([1, 1.55], gap="large")
    with queue_col:
        st.subheader("Processed inbox")
        selected_filter = st.radio(
            "Filter results",
            ["All", "Officer queue", "Drafted", "Draft failures", "Redirects"],
            horizontal=True,
            label_visibility="collapsed",
            key="result_filter",
        )
        visible = [state for state in states if _matches_filter(state, selected_filter)]
        visible_ids = {state.email.id for state in visible}
        if st.session_state.get("result_selected") not in visible_ids:
            st.session_state["result_selected"] = visible[0].email.id if visible else None
        st.caption(f"{len(visible)} of {len(states)} messages")
        if not visible:
            st.info("No messages match this filter.")
        _result_list(visible)

    with detail_col:
        selected_id = st.session_state.get("result_selected")
        selected_state = next(
            (row for row in states if row.email.id == selected_id), None
        )
        if selected_state is None:
            st.info("Select a processed email to review it.")
        else:
            _email_heading(selected_state.email)
            status, _ = _state_status(selected_state)
            if selected_state.in_human_queue:
                st.warning(status, icon="⚠️")
            else:
                decision = selected_state.decision
                confidence = decision.confidence if decision is not None else 0.0
                st.success(f"{status} · routing confidence {confidence:.2f}")

            predicted = (
                selected_state.classification.label
                if selected_state.classification is not None
                else "—"
            )
            decision = selected_state.decision
            metadata_cols = st.columns(3)
            metadata_cols[0].caption(f"**Class**\n\n{_pretty(predicted)}")
            metadata_cols[1].caption(
                f"**Route**\n\n{_pretty(decision.action) if decision is not None else '—'}"
            )
            metadata_cols[2].caption(
                "**Flags**\n\n"
                + (
                    ", ".join(_pretty(flag) for flag in decision.flags)
                    if decision is not None and decision.flags
                    else "—"
                )
            )

            scrub = selected_state.scrub
            if scrub is not None and scrub.redacted_count:
                kinds = " | ".join(
                    f"{_pretty(kind)}: {count}"
                    for kind, count in sorted(scrub.counts.items())
                )
                st.info(
                    f"Privacy shield: {scrub.redacted_count} sensitive "
                    f"value{'s' if scrub.redacted_count != 1 else ''} scrubbed locally "
                    f"({kinds})."
                )
                with st.expander("View the classifier-safe message"):
                    st.caption(
                        "This redacted copy was used for classification and any external "
                        "drafting call. The replacement vault remained on this machine."
                    )
                    st.code(scrub.text, language=None, wrap_lines=True)

            st.markdown("**Original email**")
            st.markdown(
                '<div class="readonly-note">Received message · read-only</div>',
                unsafe_allow_html=True,
            )
            _read_only_email(selected_state.email)
            st.caption(
                "The original remains unchanged. The classifier and external drafter saw only "
                "the locally scrubbed version."
            )
            st.divider()
            _render_draft(selected_state)
            _render_procedure(selected_state)

    _render_risk_coverage()


# --------------------------------------------------------------------------- #
# App entry
# --------------------------------------------------------------------------- #


try:
    mailbox = _mailbox(DEFAULT_SPLIT, DEFAULT_LIMIT)
except Exception as exc:  # noqa: BLE001 -- load failures need a usable page
    st.error(f"The demonstration inbox could not be loaded: {type(exc).__name__}: {exc}")
    st.stop()

current_stage = _stage()
if current_stage == "inbox":
    _render_inbox(mailbox)
elif current_stage == "processing":
    _render_processing(mailbox)
else:
    completed_states: list[TriageState] = list(st.session_state.get("processed_states", []))
    if not completed_states:
        st.session_state["workflow_stage"] = "inbox"
        st.rerun()
    _render_results(completed_states)
