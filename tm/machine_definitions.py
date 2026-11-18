"""Machine definitions (pure data) for the simulator.

A machine is the 7-tuple  M = (Q, Σ, Γ, δ, q0, B, F)  plus one explicit
rejecting halt state.

    δ : (state, read_symbol) -> (next_state, write_symbol, direction)

Conventions used by BOTH machines
---------------------------------
* B is the blank symbol. B is in Γ but NOT in Σ.
* F = {q_accept}. The machine ACCEPTS iff it enters q_accept.
* q_reject is an explicit rejecting halt state. The machine REJECTS iff it
  enters q_reject.
* q_accept and q_reject have no outgoing transitions; entering either halts.
* δ is TOTAL on (Q \\ {q_accept, q_reject}) × Γ. Every "this input is wrong"
  case is an explicit transition into q_reject (it is stored in δ, and shown in
  the transition table and diagram). Nothing is invented at run time: if the
  engine ever finds a missing entry it reports UNDEFINED TRANSITION, never
  ACCEPT or REJECT.
* Empty input is a valid input (the empty string is over Σ). Both machines
  read B in q0 and move to q_reject, because n ≥ 1 is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, NamedTuple, Tuple

from . import gstin_machine as _gstin
from .tape import DIRECTIONS

Rule = Tuple[str, str, str]  # (next_state, write_symbol, direction)


class TransitionRow(NamedTuple):
    state: str
    read: str
    write: str
    move: str
    next_state: str


@dataclass(frozen=True, eq=False)
class MachineDefinition:
    """Immutable description of a deterministic single-tape Turing Machine."""

    key: str
    states: Tuple[str, ...]
    input_alphabet: Tuple[str, ...]
    tape_alphabet: Tuple[str, ...]
    transitions: Mapping[Tuple[str, str], Rule]
    initial_state: str
    blank: str
    accept_states: Tuple[str, ...]
    reject_states: Tuple[str, ...]
    # Presentation-only metadata (never used by the engine).
    label: str = ""
    language_latex: str = ""
    explanation: str = ""
    marking_strategy: str = ""
    state_notes: Mapping[str, str] = field(default_factory=dict)
    accept_label: str = "ACCEPTED"           # wording for the accepting halt
    reject_label: str = "REJECTED"           # wording for the rejecting halt
    default_step_limit: int = 10_000         # suggested limit for Run in the UI
    examples: str = ""                       # example inputs shown under the input box
    default_input: str = "0011"              # initial text in the input box
    disclaimer: str = ""                     # caveat shown with the result
    # Verdict cells: label -> tape position, written by the machine itself.
    result_cells: Mapping[str, int] = field(default_factory=dict)
    pass_symbol: str = ""
    fail_symbol: str = ""
    # Grouping of states into phases (used only to draw readable diagrams).
    phases: Mapping[str, str] = field(default_factory=dict)
    phase_order: Tuple[str, ...] = ()
    phase_notes: Mapping[str, str] = field(default_factory=dict)
    # Rules added only to make δ total that the design never reaches
    # (verified by tests). Hidden from the diagram by default, flagged in the table.
    defensive_transitions: frozenset = frozenset()

    def __post_init__(self) -> None:
        self.validate()

    # ------------------------------------------------------------ validation
    def validate(self) -> None:
        Q, Sigma, Gamma = set(self.states), set(self.input_alphabet), set(self.tape_alphabet)
        halting = set(self.accept_states) | set(self.reject_states)
        if len(Q) != len(self.states):
            raise ValueError("Duplicate states.")
        if len(Gamma) != len(self.tape_alphabet):
            raise ValueError("Duplicate tape symbols.")
        if self.initial_state not in Q:
            raise ValueError("Initial state is not in Q.")
        if not halting <= Q:
            raise ValueError("Accepting/rejecting states must be in Q.")
        if set(self.accept_states) & set(self.reject_states):
            raise ValueError("A state cannot be both accepting and rejecting.")
        if self.blank not in Gamma:
            raise ValueError("The blank symbol must be in Γ.")
        if self.blank in Sigma:
            raise ValueError("The blank symbol must not be in Σ.")
        if not Sigma <= Gamma:
            raise ValueError("Σ must be a subset of Γ.")
        for (q, a), (nq, w, d) in self.transitions.items():
            if q not in Q or nq not in Q:
                raise ValueError(f"Transition ({q}, {a}) uses a state outside Q.")
            if q in halting:
                raise ValueError(f"Halting state {q} must not have outgoing transitions.")
            if a not in Gamma or w not in Gamma:
                raise ValueError(f"Transition ({q}, {a}) uses a symbol outside Γ.")
            if d not in DIRECTIONS:
                raise ValueError(f"Transition ({q}, {a}) has invalid direction {d!r}.")
        if not set(self.phases) <= Q:
            raise ValueError("Phases refer to states outside Q.")
        if not set(self.defensive_transitions) <= set(self.transitions):
            raise ValueError("Defensive transitions must be defined transitions.")

    # -------------------------------------------------------------- queries
    @property
    def halting_states(self) -> Tuple[str, ...]:
        return tuple(self.accept_states) + tuple(self.reject_states)

    def missing_transitions(self) -> List[Tuple[str, str]]:
        """(state, symbol) pairs of non-halting states that have no rule."""
        halting = set(self.halting_states)
        return [
            (q, a)
            for q in self.states if q not in halting
            for a in self.tape_alphabet if (q, a) not in self.transitions
        ]

    def sorted_transitions(self) -> List[TransitionRow]:
        """Every defined transition, sorted by (state order, symbol order)."""
        s_idx = {s: i for i, s in enumerate(self.states)}
        a_idx = {a: i for i, a in enumerate(self.tape_alphabet)}
        keys = sorted(self.transitions, key=lambda k: (s_idx[k[0]], a_idx[k[1]]))
        return [TransitionRow(q, a, *self._unpack(self.transitions[(q, a)])) for q, a in keys]

    @staticmethod
    def _unpack(rule: Rule) -> Tuple[str, str, str]:
        nq, w, d = rule
        return w, d, nq


def _complete_with_reject(
    explicit: Dict[Tuple[str, str], Rule],
    states: Tuple[str, ...],
    tape_alphabet: Tuple[str, ...],
    halting: Tuple[str, ...],
    reject_state: str,
) -> Dict[Tuple[str, str], Rule]:
    """Make δ total by adding explicit (q, a) -> (q_reject, a, R) entries.

    This runs ONCE when the definition is built; the result is an ordinary
    dictionary that the engine, table, and diagram all read.
    """
    full = dict(explicit)
    for q in states:
        if q in halting:
            continue
        for a in tape_alphabet:
            full.setdefault((q, a), (reject_state, a, "R"))
    return full


# ======================================================================
# Machine A:  L1 = { 0^n 1^n | n >= 1 }
# ======================================================================
# Marking strategy: X marks a matched 0, Y marks a matched 1.
#   Each round turns the leftmost unmarked 0 into X, then the leftmost
#   unmarked 1 into Y. When no unmarked 0 is left, only Y's may remain.
_L1_STATES = ("q0", "q1", "q2", "q3", "q_accept", "q_reject")
_L1_GAMMA = ("0", "1", "X", "Y", "B")
_L1_EXPLICIT: Dict[Tuple[str, str], Rule] = {
    # q0: head on the leftmost unmarked position
    ("q0", "0"): ("q1", "X", "R"),          # mark a 0, go find its 1
    ("q0", "Y"): ("q3", "Y", "R"),          # no 0 left -> verify only Y's remain
    # q1: scan right for the first unmarked 1
    ("q1", "0"): ("q1", "0", "R"),
    ("q1", "Y"): ("q1", "Y", "R"),
    ("q1", "1"): ("q2", "Y", "L"),          # mark the 1, go back left
    # q2: scan left back to the X
    ("q2", "0"): ("q2", "0", "L"),
    ("q2", "Y"): ("q2", "Y", "L"),
    ("q2", "X"): ("q0", "X", "R"),          # step right of X, start next round
    # q3: verify that the rest of the tape is Y* followed by blank
    ("q3", "Y"): ("q3", "Y", "R"),
    ("q3", "B"): ("q_accept", "B", "R"),
}

L1_MACHINE = MachineDefinition(
    key="L1",
    states=_L1_STATES,
    input_alphabet=("0", "1"),
    tape_alphabet=_L1_GAMMA,
    transitions=_complete_with_reject(
        _L1_EXPLICIT, _L1_STATES, _L1_GAMMA, ("q_accept", "q_reject"), "q_reject"
    ),
    initial_state="q0",
    blank="B",
    accept_states=("q_accept",),
    reject_states=("q_reject",),
    label="L1: {0ⁿ1ⁿ | n ≥ 1}",
    language_latex=r"L_1 = \{\, 0^n 1^n \mid n \ge 1 \,\}",
    explanation=(
        "Strings made of n zeros followed by exactly n ones, with n at least 1. "
        "Examples in L1: 01, 0011, 000111. Not in L1: the empty string, 001, 011, "
        "0101, 111000."
    ),
    marking_strategy=(
        "X marks a matched 0 and Y marks a matched 1. In each round the machine "
        "marks the leftmost unmarked 0 as X, scans right to the leftmost unmarked "
        "1 and marks it Y, then returns to the X. When q0 finds a Y instead of a 0, "
        "all zeros are matched, so q3 checks that only Y's remain before the blank."
    ),
    state_notes={
        "q0": "Start of a round: mark a 0 as X, or (on Y) begin the final check",
        "q1": "Scan right to the first unmarked 1",
        "q2": "Scan left back to the last X",
        "q3": "Final check: only Y's up to the blank",
        "q_accept": "Accepting halt state",
        "q_reject": "Rejecting halt state",
    },
)


# ======================================================================
# Machine B:  L2 = { 0^n 1^n 2^n | n >= 1 }
# ======================================================================
# Marking strategy: X marks a matched 0, Y a matched 1, Z a matched 2.
#   Each round marks one 0, one 1 and one 2, in that order. When no unmarked
#   0 is left, the tape must be exactly X* Y* Z* (checked by q4, q5).
_L2_STATES = ("q0", "q1", "q2", "q3", "q4", "q5", "q_accept", "q_reject")
_L2_GAMMA = ("0", "1", "2", "X", "Y", "Z", "B")
_L2_EXPLICIT: Dict[Tuple[str, str], Rule] = {
    # q0: head on the leftmost unmarked position
    ("q0", "0"): ("q1", "X", "R"),          # mark a 0
    ("q0", "Y"): ("q4", "Y", "R"),          # no 0 left -> verify Y* Z* B
    # q1: scan right for the first unmarked 1 (skipping 0's and Y's)
    ("q1", "0"): ("q1", "0", "R"),
    ("q1", "Y"): ("q1", "Y", "R"),
    ("q1", "1"): ("q2", "Y", "R"),          # mark the 1
    # q2: scan right for the first unmarked 2 (skipping 1's and Z's)
    ("q2", "1"): ("q2", "1", "R"),
    ("q2", "Z"): ("q2", "Z", "R"),
    ("q2", "2"): ("q3", "Z", "L"),          # mark the 2, go back
    # q3: scan left back to the last X
    ("q3", "0"): ("q3", "0", "L"),
    ("q3", "1"): ("q3", "1", "L"),
    ("q3", "Y"): ("q3", "Y", "L"),
    ("q3", "Z"): ("q3", "Z", "L"),
    ("q3", "X"): ("q0", "X", "R"),          # step right of X, start next round
    # q4: verification, skipping the Y's
    ("q4", "Y"): ("q4", "Y", "R"),
    ("q4", "Z"): ("q5", "Z", "R"),
    # q5: verification, skipping the Z's until the blank
    ("q5", "Z"): ("q5", "Z", "R"),
    ("q5", "B"): ("q_accept", "B", "R"),
}

L2_MACHINE = MachineDefinition(
    key="L2",
    states=_L2_STATES,
    input_alphabet=("0", "1", "2"),
    tape_alphabet=_L2_GAMMA,
    transitions=_complete_with_reject(
        _L2_EXPLICIT, _L2_STATES, _L2_GAMMA, ("q_accept", "q_reject"), "q_reject"
    ),
    initial_state="q0",
    blank="B",
    accept_states=("q_accept",),
    reject_states=("q_reject",),
    default_input="001122",
    label="L2: {0ⁿ1ⁿ2ⁿ | n ≥ 1}",
    language_latex=r"L_2 = \{\, 0^n 1^n 2^n \mid n \ge 1 \,\}",
    explanation=(
        "Strings made of n zeros, then n ones, then n twos, with n at least 1. "
        "Examples in L2: 012, 001122, 000111222. Not in L2: the empty string, "
        "00112, 001222, 0122, 102, 00011222. (L2 is not context-free, but a "
        "Turing Machine can recognize it.)"
    ),
    marking_strategy=(
        "X marks a matched 0, Y a matched 1, Z a matched 2. Each round marks the "
        "leftmost unmarked 0 (q0), the next unmarked 1 to its right (q1), and the "
        "next unmarked 2 to the right of that (q2), then returns to the X (q3). "
        "When q0 meets a Y, no 0 is left, and q4/q5 check that the remainder is "
        "exactly Y's, then Z's, then blank. Any stray 0, 1 or 2 there, or a missing "
        "symbol during a round, leads to q_reject."
    ),
    state_notes={
        "q0": "Start of a round: mark a 0 as X, or (on Y) begin the final check",
        "q1": "Scan right to the first unmarked 1",
        "q2": "Scan right to the first unmarked 2",
        "q3": "Scan left back to the last X",
        "q4": "Final check: skip Y's, expect a Z",
        "q5": "Final check: skip Z's, expect the blank",
        "q_accept": "Accepting halt state",
        "q_reject": "Rejecting halt state",
    },
)


# ======================================================================
# Machine C:  Binary palindromes   L3 = { w in {0,1}* | w = w^R }
# ======================================================================
# Marking strategy: X marks every processed cell (left end and right end).
#   Each round remembers the leftmost unprocessed symbol in the STATE
#   (q1 = remembered 0, q2 = remembered 1), marks it X, runs to the right end
#   of the unprocessed part, and compares the rightmost unprocessed symbol
#   with the remembered one. A match marks it X and returns left; a mismatch
#   rejects. The empty string and single symbols are palindromes.
_PAL_STATES = ("q0", "q1", "q2", "q3", "q4", "q5", "q_accept", "q_reject")
_PAL_GAMMA = ("0", "1", "X", "B")
_PAL_EXPLICIT: Dict[Tuple[str, str], Rule] = {
    # q0: head on the leftmost unprocessed cell (or on processed cells / blank)
    ("q0", "0"): ("q1", "X", "R"),          # remember 0, mark it
    ("q0", "1"): ("q2", "X", "R"),          # remember 1, mark it
    ("q0", "X"): ("q_accept", "X", "R"),    # nothing unprocessed is left: palindrome
    ("q0", "B"): ("q_accept", "B", "R"),    # empty input: palindrome
    # q1: carrying 0, run right to the end of the unprocessed part
    ("q1", "0"): ("q1", "0", "R"),
    ("q1", "1"): ("q1", "1", "R"),
    ("q1", "X"): ("q3", "X", "L"),          # hit processed cell: step back onto last unprocessed
    ("q1", "B"): ("q3", "B", "L"),          # hit blank: step back onto last unprocessed
    # q2: carrying 1, same movement
    ("q2", "0"): ("q2", "0", "R"),
    ("q2", "1"): ("q2", "1", "R"),
    ("q2", "X"): ("q4", "X", "L"),
    ("q2", "B"): ("q4", "B", "L"),
    # q3: compare rightmost unprocessed symbol with the remembered 0
    ("q3", "0"): ("q5", "X", "L"),          # match: mark it, go back left
    ("q3", "X"): ("q_accept", "X", "R"),    # we stepped back onto our own mark: odd-length middle
    #   (q3, 1) -> q_reject               (mismatch; explicit rejecting transition below)
    # q4: compare with the remembered 1
    ("q4", "1"): ("q5", "X", "L"),
    ("q4", "X"): ("q_accept", "X", "R"),
    #   (q4, 0) -> q_reject               (mismatch)
    # q5: return left to the last left-end mark
    ("q5", "0"): ("q5", "0", "L"),
    ("q5", "1"): ("q5", "1", "L"),
    ("q5", "X"): ("q0", "X", "R"),          # step right of the mark: next round
}

PAL_MACHINE = MachineDefinition(
    key="PAL",
    states=_PAL_STATES,
    input_alphabet=("0", "1"),
    tape_alphabet=_PAL_GAMMA,
    transitions=_complete_with_reject(
        _PAL_EXPLICIT, _PAL_STATES, _PAL_GAMMA, ("q_accept", "q_reject"), "q_reject"
    ),
    initial_state="q0",
    blank="B",
    accept_states=("q_accept",),
    reject_states=("q_reject",),
    default_input="1001",
    label="L3: Binary Palindrome {w ∈ {0,1}* | w = wᴿ}",
    language_latex=r"L_3 = \{\, w \in \{0,1\}^* \mid w = w^R \,\}",
    explanation=(
        "Binary strings that read the same forwards and backwards. The empty string "
        "is a palindrome and is accepted. Accepted: (empty), 0, 1, 00, 11, 101, 1001, "
        "0110, 01010. Rejected: 01, 10, 100, 1101, 0010."
    ),
    marking_strategy=(
        "X marks processed cells. q0 reads the leftmost unprocessed symbol, remembers it "
        "in the state (q1 = 0, q2 = 1) and marks it X. The head runs right to the end of the "
        "unprocessed part, steps back, and q3/q4 compare the rightmost unprocessed symbol "
        "with the remembered one. On a match it is marked X and q5 returns left to the last "
        "mark. If the head steps back onto its own left mark, nothing is left to compare "
        "(odd-length middle) and the machine accepts; if q0 meets a mark or blank, all "
        "symbols are paired and it accepts. Any mismatch goes to q_reject."
    ),
    state_notes={
        "q0": "Start of a round: remember and mark the leftmost unprocessed symbol (blank/X: accept)",
        "q1": "Carrying 0: run right to the end of the unprocessed part",
        "q2": "Carrying 1: run right to the end of the unprocessed part",
        "q3": "Compare the rightmost unprocessed symbol with the remembered 0",
        "q4": "Compare the rightmost unprocessed symbol with the remembered 1",
        "q5": "Return left to the last left-end mark",
        "q_accept": "Accepting halt state",
        "q_reject": "Rejecting halt state",
    },
    examples="Try: (empty), 0, 101, 1001, 01010 (accepted); 01, 100, 1101, 0010 (rejected).",
)


# ======================================================================
# Machine D:  GSTIN Validator (15 characters, over 0-9 and A-Z)
# ======================================================================
# The rule table is built in tm/gstin_machine.py (see its docstring for the
# tape layout and the five format-validation passes).
_GSTIN_SPEC = _gstin.build_gstin_spec()
_GSTIN_FULL = _complete_with_reject(
    dict(_GSTIN_SPEC.rules), _GSTIN_SPEC.states, _gstin.GAMMA,
    ("q_accept", "q_reject"), "q_reject",
)
GSTIN_EXPLICIT_TRANSITIONS = frozenset(_GSTIN_SPEC.rules)

GSTIN_MACHINE = MachineDefinition(
    key="GSTIN",
    states=_GSTIN_SPEC.states,
    input_alphabet=_gstin.SIGMA,
    tape_alphabet=_gstin.GAMMA,
    transitions=_GSTIN_FULL,
    initial_state="q0",
    blank=_gstin.BLANK,                      # "_": the letter B belongs to the input alphabet
    accept_states=("q_accept",),
    reject_states=("q_reject",),
    default_input="27AAPFU0939F1ZV",
    label="GSTIN Format Validator (15 characters)",
    language_latex=(
        r"L_{GSTIN} = \{\, s \in \{0\text{-}9, A\text{-}Z\}^{15} \mid "
        r"\text{state}(s_{1}s_{2}) \wedge \text{PAN}(s_{3..12}) \wedge s_{13} \neq 0 "
        r"\wedge s_{14} = Z \,\}"
    ),
    explanation=(
        "A GSTIN has 15 characters: a 2-digit state/UT code (01-38, 97, 99), a 10-character PAN "
        "(5 letters, 4 digits, 1 letter), an entity number (1-9 or A-Z), the letter Z, and any "
        "digit or uppercase letter in position 15. The machine runs five format-validation passes, "
        "records a ✓ or ✗ verdict cell on its own tape for each, and accepts only if all are ✓. "
        "Inputs containing symbols other than 0-9 and A-Z (such as lowercase letters or spaces) "
        "are rejected before execution as INVALID INPUT."
    ),
    marking_strategy="Verdict cells ✓/✗ are appended to the left of the sentinel '<'.",
    state_notes={},
    accept_label="VALID GSTIN",
    reject_label="INVALID GSTIN",
    default_step_limit=10_000,
    examples=(
        "Try: 27AAPFU0939F1AV (default character not Z); position 15 may be any digit or letter."
    ),
    disclaimer=(
        "A VALID GSTIN result means only that the format is correct. It does not confirm that the "
        "check digit is correct or that the GSTIN is registered, active, or belongs to the stated "
        "business; registration can only be confirmed on the official GST portal."
    ),
    result_cells=_gstin.RESULT_CELLS,
    pass_symbol=_gstin.OK,
    fail_symbol=_gstin.BAD,
    phases=_GSTIN_SPEC.phases,
    phase_order=_gstin.PHASE_ORDER,
    phase_notes=_gstin.PHASE_NOTES,
    defensive_transitions=frozenset(set(_GSTIN_FULL) - set(_GSTIN_SPEC.rules)),
)


MACHINES: Dict[str, MachineDefinition] = {
    "L1": L1_MACHINE,
    "L2": L2_MACHINE,
    "PAL": PAL_MACHINE,
    "GSTIN": GSTIN_MACHINE,
}


def get_machine(key: str) -> MachineDefinition:
    return MACHINES[key]
