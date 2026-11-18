"""Interactive Turing Machine Simulator (Streamlit front end).

All computation happens in `tm.engine.TuringMachine`; this file only displays
the engine's state and forwards the Run / Step / Reset buttons to it.
"""

import pandas as pd
import streamlit as st

from tm import MACHINES, Status, TuringMachine
from tm.visualization import (
    grouped_transition_rows,
    tape_html,
    tape_window,
    to_dot,
    to_phase_overview_dot,
)

st.set_page_config(page_title="Interactive Turing Machine Simulator", layout="wide")


# ----------------------------------------------------------- session state
def sync_engine(machine_key: str, input_text: str) -> TuringMachine:
    """Return the engine for (machine, input), rebuilding it if either changed.

    The engine lives in st.session_state so Streamlit reruns do not reset or
    repeat the computation. A new machine or a new input always starts from a
    fresh initial configuration, so no stale state is ever reused.
    """
    signature = (machine_key, input_text)
    if st.session_state.get("signature") != signature:
        st.session_state["engine"] = TuringMachine(MACHINES[machine_key], input_text)
        st.session_state["signature"] = signature
    return st.session_state["engine"]


# ------------------------------------------------------------------ header
st.title("Interactive Turing Machine Simulator")
st.caption("A visual exploration of Turing Machines and formal language recognition.")

# ------------------------------------------------- B: machine selection
st.subheader("1. Select a language")
machine_key = st.selectbox(
    "Language", options=list(MACHINES), format_func=lambda k: MACHINES[k].label
)
definition = MACHINES[machine_key]
st.latex(definition.language_latex)
st.write(definition.explanation)

states_text = (
    "{" + ", ".join(definition.states) + "}"
    if len(definition.states) <= 20
    else f"{len(definition.states)} states (grouped into phases below)"
)
with st.expander("Formal definition  M = (Q, Σ, Γ, δ, q₀, B, F)  and marking strategy"):
    st.markdown(
        f"- **Q** = {states_text}\n"
        f"- **Σ** = {{{', '.join(definition.input_alphabet)}}}\n"
        f"- **Γ** = {{{', '.join(definition.tape_alphabet)}}}\n"
        f"- **q₀** = {definition.initial_state}\n"
        f"- **B** = {definition.blank} (blank; not in Σ)\n"
        f"- **F** = {{{', '.join(definition.accept_states)}}} (accepting); "
        f"**{', '.join(definition.reject_states)}** is the explicit rejecting halt state\n"
        f"- **δ**: (state, read) → (next state, write, direction); "
        f"{len(definition.transitions)} transitions, listed in section 7."
    )
    st.markdown("**Marking strategy.** " + definition.marking_strategy)
    if definition.phase_notes:
        st.markdown("**Phases** (groups of states; the machine runs them in this order)")
        for phase in definition.phase_order:
            n = sum(1 for ph in definition.phases.values() if ph == phase)
            st.markdown(f"- **{phase}** ({n} states): {definition.phase_notes.get(phase, '')}")
    else:
        st.markdown("**State roles**")
        for state, note in definition.state_notes.items():
            st.markdown(f"- `{state}`: {note}")

# ------------------------------------------------------------ C: input
st.subheader("2. Enter an input string")
input_text = st.text_input(
    "Input string",
    value=definition.default_input,
    key=f"input_text_{machine_key}",
    help="Leave empty to test the empty string. Press Enter to load a new input.",
)
if definition.examples:
    st.caption(definition.examples)
engine = sync_engine(machine_key, input_text)

c_run, c_step, c_reset, c_limit = st.columns([1, 1, 1, 2])
run_clicked = c_run.button("Run", width="stretch", type="primary")
step_clicked = c_step.button("Step", width="stretch")
reset_clicked = c_reset.button("Reset", width="stretch")
step_limit = c_limit.number_input(
    "Step limit for Run",
    min_value=1,
    max_value=1_000_000,
    value=definition.default_step_limit,
    step=100,
    key=f"step_limit_{machine_key}",
)

# Buttons act on the engine BEFORE anything is rendered, so the display below
# always shows the post-click configuration (and history is never duplicated:
# it is rendered from the engine, not appended to on each rerun).
if run_clicked:
    engine.run(max_steps=int(step_limit))
elif step_clicked:
    engine.step()
elif reset_clicked:
    engine.reset()

# ------------------------------------------------------------ D: result
st.subheader("3. Result")
status = engine.status
if status == Status.ACCEPTED:
    st.success(f"**{definition.accept_label}**")
elif status == Status.REJECTED:
    st.error(f"**{definition.reject_label}**")
elif status == Status.INVALID_INPUT:
    bad = ", ".join(repr(c) for c in engine.invalid_symbols)
    allowed = ", ".join(definition.input_alphabet)
    extra = (
        f" Treated as {definition.reject_label}."
        if definition.reject_label != "REJECTED" else ""
    )
    st.warning(
        f"**INVALID INPUT**: symbol(s) {bad} are not in Σ = {{{allowed}}}. "
        f"Nothing was executed.{extra}"
    )
elif status == Status.TIMEOUT:
    st.warning(
        f"**TIMEOUT (STEP LIMIT EXCEEDED)**: stopped after {engine.steps} transitions. "
        "This is not a rejection; the machine has not halted. Press Run or Step to continue."
    )
elif status == Status.UNDEFINED_TRANSITION:
    st.error(f"**UNDEFINED TRANSITION**: {engine.error} (machine definition error, not a rejection)")
elif engine.steps == 0:
    st.info("**READY**: press Step to execute one transition, or Run to execute until the machine halts.")
else:
    st.info("**RUNNING**: paused between transitions. Press Step or Run to continue.")

m1, m2, m3 = st.columns(3)
m1.metric("Transitions executed", engine.steps)
m2.metric("Final state" if engine.halted else "Current state", engine.state)
m3.metric("Halted normally", "Yes" if engine.halted_normally else "No")

if definition.result_cells:
    st.markdown("**Validation checks** (read from the verdict cells the machine wrote on its tape)")
    config_now = engine.get_configuration()
    check_rows = []
    for label, position in definition.result_cells.items():
        symbol = config_now.symbol_at(position)
        if symbol == definition.pass_symbol:
            outcome = f"{definition.pass_symbol} PASS"
        elif symbol == definition.fail_symbol:
            outcome = f"{definition.fail_symbol} FAIL"
        elif status == Status.INVALID_INPUT:
            outcome = "Not evaluated (invalid input)"
        elif engine.halted:
            outcome = "Not evaluated"
        else:
            outcome = "Pending"
        check_rows.append({"Check": label, "Tape cell": position, "Result": outcome})
    st.dataframe(pd.DataFrame(check_rows), hide_index=True)
if definition.disclaimer:
    st.caption(definition.disclaimer)

# --------------------------------------------------------- E: tape
st.subheader("4. Tape")
if status == Status.INVALID_INPUT:
    st.caption("No tape is shown because the input was rejected before execution.")
else:
    config = engine.get_configuration()
    t1, t2, t3 = st.columns(3)
    t1.markdown(f"**State:** `{config.state}`")
    t2.markdown(f"**Step:** `{config.step}`")
    t3.markdown(f"**Head position:** `{config.head}`  (reading `{config.head_symbol}`)")
    if definition.phases:
        st.markdown(f"**Phase:** {definition.phases.get(config.state, '')}")
    st.markdown(tape_html(tape_window(config, max_cells=31), definition), unsafe_allow_html=True)
    st.caption(
        "Yellow = cell under the head. Blue = marker symbols (X, Y, Z). "
        "Faded = blank. Numbers below the cells are tape positions (the input starts at 0)."
    )

    nxt = engine.next_transition()
    if nxt is not None:
        state, read, rule = nxt
        if rule is not None:
            st.markdown(
                f"**Next transition:** `({state}, {read}) → ({rule[0]}, {rule[1]}, {rule[2]})`"
            )
        else:
            st.markdown(f"**Next transition:** none defined for `({state}, {read})`")
    elif engine.halted_normally:
        st.markdown("**Next transition:** none (the machine has halted).")

# ----------------------------------------------------- F: history
st.subheader("5. Transition history")
history = engine.history
if history:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Step": r.step,
                    "State Before": r.state_before,
                    "Read": r.read,
                    "Write": r.write,
                    "Move": r.move,
                    "State After": r.state_after,
                    "Transition": r.as_text(),
                }
                for r in history
            ]
        ),
        hide_index=True,
        height=min(400, 36 * (len(history) + 1) + 3),
    )
else:
    st.caption("No transitions executed yet.")

# --------------------------------------------------- G: diagram
st.subheader("6. State transition diagram")
diagram_state = None if status == Status.INVALID_INPUT else engine.state
if definition.phases:
    # Large machine: show one phase at a time (or the phase overview).
    views = ["Overview"] + list(definition.phase_order)
    view = st.selectbox(
        "Diagram view",
        views,
        help="The machine has many states, so it is drawn one phase at a time. "
             "All views are generated from the same transition table.",
    )
    if view == "Overview":
        dot = to_phase_overview_dot(definition, current_state=diagram_state)
    else:
        dot = to_dot(definition, current_state=diagram_state, compact_labels=True, phase=view)
    st.graphviz_chart(dot, width="stretch")
    st.caption(
        "Edge labels are read symbols / write symbol, move (Σ = the input alphabet). "
        "Green double circle = accepting; red box = rejecting; dashed grey boxes belong to a "
        "different phase; thick orange outline = current state (or current phase in the overview). "
        "Rules that only make δ total and are never executed are not drawn."
    )
else:
    collapse = st.checkbox(
        "Group transitions into q_reject (one dashed edge per state)",
        value=True,
        help="Display option only: the same transitions are drawn either way.",
    )
    st.graphviz_chart(
        to_dot(definition, current_state=diagram_state, collapse_rejects=collapse),
        width="stretch",
    )
    st.caption(
        "Edge labels are read/write,move. Arrow from the dot marks the initial state; "
        "double green circle = accepting; red box = rejecting; thick orange outline = current state; "
        "dashed red edges lead to q_reject."
    )

# ------------------------------------------------------ H: table
st.subheader("7. Transition table")
many = len(definition.transitions) > 300
grouped = st.checkbox(
    "Compact view (group rows that share state, next state, move and write rule)",
    value=many,
    help="Display option only. Untick to list every individual transition "
         f"({len(definition.transitions)} for this machine).",
)
if grouped:
    table_rows = grouped_transition_rows(definition)
else:
    table_rows = [
        {
            "Current State": r.state,
            "Read Symbol": r.read,
            "Write Symbol": r.write,
            "Direction": r.move,
            "Next State": r.next_state,
            **(
                {"Note": "totality filler (never executed)"
                 if (r.state, r.read) in definition.defensive_transitions else ""}
                if definition.defensive_transitions else {}
            ),
        }
        for r in definition.sorted_transitions()
    ]
st.dataframe(pd.DataFrame(table_rows), hide_index=True, height=420)
st.caption(
    f"{len(definition.transitions)} transitions in total"
    + (f" ({len(table_rows)} rows in this compact view)." if grouped else ".")
    + f" Accepting state(s): {', '.join(definition.accept_states)}; "
    f"rejecting state(s): {', '.join(definition.reject_states)}. "
    "Halting states have no outgoing transitions: the machine stops as soon as it enters one."
    + (" Rows marked as totality filler exist only so that δ is defined for every (state, symbol) "
       "pair; tests confirm they are never executed." if definition.defensive_transitions else "")
)
