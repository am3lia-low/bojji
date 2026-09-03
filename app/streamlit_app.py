"""The officer's queue -- the demo UI.

RUNTIME. Run with::

    streamlit run app/streamlit_app.py

**This is the officer's view, not a chatbot.** The human queue is where a reviewer
actually works, so the screen is organised around the two things they do: confirm
what was automated, and act on what was not. An escalated item is therefore not a
failure state to be hidden -- it is the primary content (``BUILD.md`` S5.9).

Three commitments the layout makes good on:

* **Every escalated item carries a reason chip.** An officer sorting a queue needs
  to know why an item is in front of them before they open it, and the reason is
  closed vocabulary rather than free text, so the queue can be grouped by it.
* **The SOP pane renders the retrieved procedure in full.** This is what makes a
  drafting failure workable rather than dead: the officer writes the reply from the
  same source the drafter would have used.
* **Drafts are live.** Free-tier rate limits are visible here rather than hidden --
  a rate-limited item shows its failure reason and its SOP, which is the designed
  behaviour and not a defect to apologise for.

The risk-coverage slider re-routes already-classified items through the REAL router
at a new threshold multiplier. Nothing is re-classified, so the slider is instant
and the curve it traces is the one the system would actually follow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import split  # noqa: E402

from triage.graph import build_default_deps, build_graph, run_one  # noqa: E402
from triage.models.calibration import TemperatureScaler  # noqa: E402
from triage.models.encoder import ModelNotTrainedError  # noqa: E402
from triage.nodes.calibrate import calibrate, rollup  # noqa: E402
from triage.nodes.flags import detect_flags  # noqa: E402
from triage.nodes.route import load_thresholds, route  # noqa: E402
from triage.pii.scrubber import Scrubber  # noqa: E402
from triage.schemas import Action, TriageState  # noqa: E402
from triage.sop.index import build_index  # noqa: E402

RESULTS = ROOT / "eval" / "results"

st.set_page_config(
    page_title="Citizen triage — officer queue",
    layout="wide",
    initial_sidebar_state="expanded",
)

#: Queue styling. Density is the point: an officer sorting a queue wants many items
#: on screen at once, and the default Streamlit button is tall, centred and heavy.
#: These rules restyle the row buttons into flush-left list rows -- borderless, tight
#: leading, a hairline between them -- so roughly three times as many items are
#: visible without changing what a row says.
#:
#: Colour is carried by the chips rather than the rows: an escalated item is already
#: distinguished by sitting in the review queue, so tinting whole rows would spend
#: the screen's only strong colour on a distinction the tab already makes. All
#: colours are set against both themes, since a fixed palette would invert badly
#: for anyone running Streamlit in dark mode.
#: The row hook is Streamlit's own ``st-key-<key>`` class, which it stamps on the
#: element container for any keyed widget. That is a documented, stable handle;
#: matching on emotion hashes or on sibling position would break on a version bump.
#: Row keys are prefixed ``qrow-``, so these rules touch the queue and nothing else.
_QUEUE_CSS = """
<style>
/* The queue rows. Streamlit renders each as a button; these strip the button
   chrome and leave a flush-left list row. */
div[class*="st-key-qrow-"] button {
    text-align: left !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;
    padding: 5px 10px !important;
    margin: 0 !important;
    border: none !important;
    border-bottom: 1px solid rgba(128, 128, 128, 0.18) !important;
    border-radius: 0 !important;
    background: transparent !important;
    font-weight: 400 !important;
    line-height: 1.3 !important;
    min-height: 0 !important;
    height: auto !important;
}
div[class*="st-key-qrow-"] button:hover {
    background: rgba(128, 128, 128, 0.12) !important;
}
div[class*="st-key-qrow-"] button:focus {
    box-shadow: none !important;
    outline: none !important;
}
/* Collapse the gap Streamlit reserves between stacked widgets so rows sit flush. */
div[class*="st-key-qrow-"] { margin-top: -0.75rem !important; }

/* Streamlit centres a button's label with FLEXBOX, not text-align, and it does so
   on two unnamed wrappers between the button and the markdown -- a div and a span,
   both ``justify-content: center``. Overriding text-align alone leaves the label
   centred; these have to be reset to flex-start and given the full width, or they
   shrink-wrap and re-centre. */
div[class*="st-key-qrow-"] button > div,
div[class*="st-key-qrow-"] button > div > span {
    justify-content: flex-start !important;
    align-items: flex-start !important;
    width: 100% !important;
}
div[class*="st-key-qrow-"] button div[data-testid="stMarkdownContainer"] {
    width: 100% !important;
    text-align: left !important;
}

/* Line one is the subject (bold, slightly larger), line two the status and
   sender. Both live in ONE markdown paragraph separated by a hard break, so the
   status line is coloured through Streamlit's own ``:orange[...]`` markdown in
   the label rather than from here -- a <br>-separated line cannot be selected in
   CSS. */
div[class*="st-key-qrow-"] button p {
    margin: 0 !important;
    padding-left: 0 !important;
    text-indent: 0 !important;
    text-align: left !important;
    width: 100% !important;
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
}
div[class*="st-key-qrow-"] button p strong { font-size: 0.84rem; font-weight: 600; }

/* The selected row: a left rule and a tint, so the list echoes what the detail
   pane is showing. Without this, selection lived only in session_state and the
   queue gave no sign of which item was open. */
div[class*="st-key-qrow-sel-"] button {
    background: rgba(56, 122, 223, 0.16) !important;
    box-shadow: inset 3px 0 0 0 #387adf !important;
}
div[class*="st-key-qrow-sel-"] button p { font-weight: 600 !important; }

/* The metric strip: smaller, so it reads as a status bar rather than a dashboard.
   The contribution is the queue and the curve, not these three numbers. */
div[data-testid="stMetricValue"] { font-size: 1.45rem !important; }
div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; opacity: 0.75; }

/* Tighten the top padding Streamlit reserves above the title. */
div.block-container { padding-top: 2.6rem !important; }
</style>
"""
st.markdown(_QUEUE_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Loading. Cached, because the corpus and the weights load once per session.
# --------------------------------------------------------------------------- #


@st.cache_resource
def _index() -> Any:
    return build_index()


@st.cache_resource
def _scrubber() -> Scrubber:
    return Scrubber()


@st.cache_resource
def _classifier() -> Any:
    """The fine-tuned encoder. Absent weights are a message, not a traceback."""
    from triage.models.encoder import EncoderClassifier

    return EncoderClassifier()


@st.cache_data(show_spinner="Classifying the inbox …")
def _triage(split_name: str, limit: int) -> list[dict[str, Any]]:
    """Scrub, classify, roll up and calibrate every email ONCE.

    Routing is deliberately left out: the slider re-routes these rows without
    re-classifying, which is what keeps it interactive and what guarantees the
    displayed decision comes from the real router rather than a copy of its rule.
    """
    index, scrubber, classifier = _index(), _scrubber(), _classifier()
    scaler = TemperatureScaler.load()
    bucket_of = dict(index.bucket)

    rows: list[dict[str, Any]] = []
    items = split(split_name)[:limit]
    scrubs = [scrubber.scrub(item.email.text) for item in items]
    classifications = classifier.predict_batch([s.text for s in scrubs])
    for item, scrub, classification in zip(items, scrubs, classifications, strict=True):
        bucket, summed = rollup(classification, bucket_of)
        score = calibrate(bucket, summed, scaler)
        rows.append({
            "id": item.email.id,
            "subject": item.email.subject or "(no subject)",
            "sender": item.email.sender or "unknown sender",
            "received_at": item.email.received_at,
            "body": scrub.text,
            "truth": item.label,
            "predicted": classification.label,
            "score": score,
            "flags": detect_flags(scrub.text, classification),
            "sop_ids": tuple(s.sop_id for s in index.sops_for(classification.label)),
        })
    return rows


@st.cache_resource
def _graph(multiplier: float) -> Any:
    """The compiled graph, built once per threshold multiplier.

    Rebuilding it per draft re-read the SOP corpus, re-loaded the temperature and
    re-constructed the Gemini client on every click; the deps exist to be resolved
    once at startup (``graph.py``), so caching here restores that.
    """
    return build_graph(
        build_default_deps(classifier=_classifier(), multiplier=multiplier)
    )


def _email_for(split_name: str, email_id: str) -> Any:
    """Look the email up by id rather than by position.

    Positional lookup indexed the FULL split with an offset computed inside the
    truncated ``rows`` list. They agree only while ``rows`` is an unfiltered prefix,
    so any future sort or filter of the queue would have drafted a reply to the
    wrong citizen's email -- silently, since both are valid emails.
    """
    for item in split(split_name):
        if item.email.id == email_id:
            return item.email
    raise KeyError(f"no email {email_id!r} in split {split_name!r}")


@st.cache_data
def _risk_coverage() -> dict[str, Any] | None:
    path = RESULTS / "risk_coverage.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _reason_chip(row: dict[str, Any], decision: Any) -> str:
    """One line saying why this item is in front of an officer.

    Covers all three escalation causes from ``BUILD.md`` S5.9. The threshold case
    shows both numbers, because "low confidence" without the comparison does not
    tell a reviewer whether the item was marginal or hopeless.
    """
    if decision.reason is None:
        return ""
    if decision.reason.value == "low_confidence":
        return f"low confidence {decision.confidence:.2f} < {decision.threshold:.2f}"
    return f"bucket requires review — {decision.reason.value.replace('_', ' ')}"


def _short_reason(decision: Any) -> str:
    """The reason chip, abbreviated to fit one queue row.

    The full sentence from :func:`_reason_chip` is what the detail pane shows; a
    row has one line, so the threshold case keeps both numbers -- which is the part
    that tells a reviewer whether the item was marginal -- and the structural cases
    drop the "bucket requires review" preamble, since sitting in the review queue
    already says that. The vocabulary stays closed either way, so the queue can
    still be grouped by it.
    """
    if decision.reason is None:
        return ""
    if decision.reason.value == "low_confidence":
        # A plain "<": the label is markdown, not HTML, so an escaped entity would
        # render literally.
        return f"{decision.confidence:.2f} < {decision.threshold:.2f}"
    return decision.reason.value.replace("_", " ")


def _queue_row(row: dict[str, Any], decision: Any, *, key_prefix: str) -> None:
    """One compact list row: subject, sender, timestamp and a status chip.

    The row is styled through its widget KEY: Streamlit stamps ``st-key-<key>`` on
    the element container, so a ``qrow-`` prefix gives the CSS above a stable hook,
    and a ``qrow-sel-`` prefix marks the open item -- which is what gives the list a
    visible selected state instead of leaving selection invisible in
    ``session_state``.

    Two lines in one label: the subject, then the routing outcome, any flags, the
    sender and the date. The outcome is coloured with Streamlit's ``:orange[...]``
    markdown rather than HTML, because a button label escapes raw markup.
    """
    selected = st.session_state.get("selected") == row["id"]
    key = f"qrow-{'sel-' if selected else ''}{key_prefix}{row['id']}"

    # Colour is carried by Streamlit's own markdown colour spans, which survive
    # inside a button label where raw HTML does not. Orange for escalation, green
    # for an auto-reply, violet for a redirect -- so the queue reads down its
    # status column without the officer parsing each line.
    if decision.action is Action.ESCALATE:
        chip_text = f":orange[{_short_reason(decision)}]"
    elif decision.action is Action.REDIRECT:
        chip_text = f":violet[redirect · {decision.confidence:.2f}]"
    else:
        chip_text = f":green[auto-reply · {decision.confidence:.2f}]"

    # The whole row is ONE button, subject and status in a single markdown label.
    # Drawing the status as a separate element above the button was tried first and
    # collides: Streamlit's inter-widget spacing cannot be negated reliably enough
    # to stack two elements into one visual row, and the chip landed on top of the
    # subject. Keeping it in the label also makes the entire row the click target.
    flag_text = "".join(f" · :red[{f.value.replace('_', ' ')}]" for f in row["flags"])
    stamp = row["received_at"].strftime("%d %b")

    if st.button(
        f"**{row['subject']}**  \n{chip_text}{flag_text} · {row['sender']} · {stamp}",
        key=key, use_container_width=True,
    ):
        st.session_state["selected"] = row["id"]
        st.rerun()


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #

st.sidebar.title("Controls")
split_name = st.sidebar.selectbox("Split", ["test", "calibration", "train"], index=0)
limit = st.sidebar.slider("Emails to load", 20, 200, 60, step=20)
multiplier = st.sidebar.slider(
    "Threshold multiplier", 0.2, 2.0, 1.0, step=0.05,
    help="Scales every per-bucket threshold. 1.0 is the configured operating point.",
)
drafting_on = st.sidebar.toggle(
    "Draft live", value=False,
    help="Calls the drafting model for the selected item. Free-tier rate limits are "
         "visible rather than hidden.",
)

thresholds = load_thresholds()
scaler = TemperatureScaler.load()
if not scaler.fitted:
    st.sidebar.warning("Calibration is not fitted — confidences are raw.")

st.sidebar.caption(
    f"temperature {scaler.temperature:.4f} · "
    f"auto_answerable threshold {thresholds.get('auto_answerable', 0.5) * multiplier:.2f}"
)


# --------------------------------------------------------------------------- #
# Route at the current multiplier
# --------------------------------------------------------------------------- #

try:
    rows = _triage(split_name, limit)
except ModelNotTrainedError as exc:
    st.error(f"The classifier is not trained yet.\n\n{exc}")
    st.caption(
        "Everything else in the pipeline is wired and will run as soon as the "
        "artefact exists — scrubbing, rollup, calibration, routing and the SOP pane "
        "all read from it."
    )
    st.stop()
except Exception as exc:  # noqa: BLE001 -- a broken pipeline is a message, not a stack
    st.error(f"Triage failed: {type(exc).__name__}: {exc}")
    st.exception(exc)
    st.stop()

index = _index()
decisions = [
    route(
        row["score"], index.sops_for(row["predicted"]), row["flags"],
        dict(thresholds), calibrated=scaler.fitted, multiplier=multiplier,
    )
    for row in rows
]

automated = [(r, d) for r, d in zip(rows, decisions, strict=True) if d.is_automated]
escalated = [(r, d) for r, d in zip(rows, decisions, strict=True) if not d.is_automated]

st.title("Citizen correspondence — officer queue")
left, middle, right = st.columns(3)
left.metric("Coverage", f"{len(automated) / max(len(rows), 1):.1%}",
            help="Share acted on without a human: auto-replies plus redirects.")
middle.metric("Auto-replied", len(automated))
right.metric("Needs review", len(escalated))


# --------------------------------------------------------------------------- #
# The two queues
# --------------------------------------------------------------------------- #

#: Queue-to-detail proportions. The queue needs enough width for a subject line to
#: survive without truncating, and the detail pane carries the SOP in full, so it
#: takes the larger share -- but not by as much as the earlier 1:1.4, which left the
#: list cramped while the detail pane sat half empty.
queue_col, detail_col = st.columns([1, 1.15], gap="medium")

with queue_col:
    auto_tab, review_tab = st.tabs(
        [f"Auto-replied ({len(automated)})", f"Needs review ({len(escalated)})"]
    )

    with auto_tab:
        if not automated:
            st.caption("Nothing was automated at this threshold.")
        for row, decision in automated:
            _queue_row(row, decision, key_prefix="a")

    with review_tab:
        if not escalated:
            st.caption("Nothing escalated at this threshold.")
        for row, decision in escalated:
            _queue_row(row, decision, key_prefix="e")


# --------------------------------------------------------------------------- #
# Detail pane
# --------------------------------------------------------------------------- #

with detail_col:
    selected_id = st.session_state.get("selected")
    pair = next(
        ((r, d) for r, d in zip(rows, decisions, strict=True) if r["id"] == selected_id),
        None,
    )

    if pair is None:
        st.info("Select an item from either queue.")
    else:
        row, decision = pair
        st.markdown(
            f"<div style='font-size:1.35rem;font-weight:650;line-height:1.3;"
            f"margin-bottom:2px'>{row['subject']}</div>"
            f"<div style='font-size:0.8rem;opacity:0.65;margin-bottom:10px'>"
            f"{row['sender']} · {row['received_at'].strftime('%d %b %Y, %H:%M')}</div>",
            unsafe_allow_html=True,
        )

        if decision.reason is not None:
            st.warning(_reason_chip(row, decision), icon="⚠️")
        else:
            st.success(f"{decision.action.value} · confidence {decision.confidence:.2f}")

        a, b, c = st.columns(3)
        a.caption(f"**Predicted**\n\n{row['predicted']}")
        b.caption(f"**Bucket**\n\n{decision.bucket.value}")
        c.caption(f"**Flags**\n\n{', '.join(f.value for f in row['flags']) or '—'}")

        st.text_area("Email (scrubbed)", row["body"], height=180, disabled=True)
        st.caption(
            "Shown scrubbed, because this is exactly what the classifier and any "
            "external call saw. Real values never leave the machine."
        )

        # --- drafting -------------------------------------------------------
        if decision.is_automated:
            if drafting_on:
                with st.spinner("Drafting …"):
                    try:
                        state = run_one(
                            _graph(multiplier),
                            TriageState(email=_email_for(split_name, row["id"])),
                        )
                        draft = state.draft
                    except Exception as exc:  # noqa: BLE001
                        draft = None
                        st.error(f"Drafting failed: {exc}")

                if draft is not None and draft.status.value == "ok":
                    st.markdown("**Draft reply**")
                    st.info(draft.text)
                    st.caption(f"Grounded on {', '.join(draft.grounded_on) or '—'}")
                elif draft is not None:
                    reason = (
                        draft.failure_reason.value if draft.failure_reason else "unknown"
                    )
                    st.error(f"draft failed: {reason}")
                    st.caption(
                        "The item still carries its SOP below, so the officer can "
                        "write the reply from the same source the drafter would have used."
                    )
            else:
                st.caption("Enable **Draft live** in the sidebar to generate a reply.")

        # --- SOP pane -------------------------------------------------------
        st.divider()
        if not row["sop_ids"]:
            st.error(
                "No supporting SOP — this class has no indexed procedure, so there is "
                "nothing to ground a reply on. The item escalates by derivation."
            )
        else:
            st.markdown(f"**Procedure — {', '.join(row['sop_ids'])}**")
            for sop_id in row["sop_ids"]:
                sop = index.by_id.get(sop_id)
                if sop is None:
                    continue
                with st.expander(f"{sop.sop_id} — {sop.title}", expanded=len(row["sop_ids"]) == 1):
                    st.markdown(sop.body)


# --------------------------------------------------------------------------- #
# Risk-coverage
# --------------------------------------------------------------------------- #

st.divider()
curve = _risk_coverage()
if curve is None:
    st.caption("Run `python eval/run_eval.py` to produce the risk-coverage curve.")
else:
    st.subheader("Risk vs coverage")
    st.caption(
        "Swept with the real router over a global threshold multiplier. Reported per "
        "topic rather than as one inbox figure: an aggregate would need a class volume "
        "mix that is unpublished and seasonal."
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
            curve["overall"], key=lambda p: abs(p["multiplier"] - multiplier)
        )
        st.caption(
            f"At multiplier {point['multiplier']:.2f} — coverage {point['coverage']:.1%}, "
            f"risk {point['risk']:.1%} over {point['n']} emails. "
            f"AURC {curve.get('aurc_overall')}"
        )
    except ImportError:
        st.caption("pandas is needed for the chart.")
