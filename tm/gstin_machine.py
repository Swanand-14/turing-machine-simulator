"""Explicit transition rules for the GSTIN Validator Turing Machine.

Everything the machine decides is decided by these transitions, executed by
the same generic engine as every other machine. This module only *builds the
rule table* (pure data). It contains no validation logic that runs at
simulation time.

Tape layout (positions are integers; the input starts at 0)
-----------------------------------------------------------
    -7 -6 -5 -4 -3 | -2 | -1 | 0 ......... 14 | 15
    DF EN PAN ST LEN|  < |  $ | 15 input chars  | _ (blank)

    '<'   left sentinel written by the machine
    '$'   unused accumulator cell, preserved by all passes
    -3..-7 verdict cells: ✓ (check passed) or ✗ (check failed), appended one
          per check, in the order Length, State code, PAN, Entity, Default Z

The blank symbol is '_' (not 'B', because B is a letter of the GSTIN alphabet).

Passes (each is a separate group of states; the head returns to the left end
between passes)
-----------------------------------------------------------------------------
    Setup      write '<' and '$' to the left of the input
    1 Length   count exactly 15 symbols with a chain of states len1..len16
    2 State    first two digits must be one of the GST state/UT codes
    3 PAN      positions 3-12: 5 letters, 4 digits, 1 letter
    4 Entity   position 13: 1-9 or A-Z (not 0)
    5 Default  position 14: Z
    Final      accept iff every verdict cell is ✓

If the length check fails the machine records ✗ and halts (the other checks
are position-based and meaningless without 15 symbols). Otherwise all four
remaining checks are evaluated independently of each other. The last character
may be any digit or uppercase letter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

Rule = Tuple[str, str, str]   # (next_state, write_symbol, direction)

DIGITS = "0123456789"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SIGMA: Tuple[str, ...] = tuple(DIGITS + LETTERS)      # input alphabet; value = index
BLANK = "_"      # NOT "B": the letter B is part of the GSTIN input alphabet
LEFT_MARK = "<"
ACC_EMPTY = "$"
DONE = "#"
OK = "✓"
BAD = "✗"
GAMMA: Tuple[str, ...] = SIGMA + (LEFT_MARK, ACC_EMPTY, DONE, OK, BAD, BLANK)

# Valid GST state / UT codes: 01-38 (25 and 28 are legacy codes that are no
# longer issued but still appear on older registrations), plus 97 (Other
# Territory) and 99 (Centre Jurisdiction).
STATE_CODES: Tuple[str, ...] = tuple(f"{n:02d}" for n in range(1, 39)) + ("97", "99")

# Verdict cell for each check (tape position), in the order the passes run.
RESULT_CELLS: Mapping[str, int] = {
    "Length check": -3,
    "State code check": -4,
    "PAN structure check": -5,
    "Entity number check": -6,
    "Default character check": -7,
}

PHASE_NOTES: Mapping[str, str] = {
    "Setup": "Writes the left sentinel '<' (position -2) and the empty accumulator '$' (position -1) to the left of the input.",
    "1. Length": "A chain of 16 states consumes exactly 15 symbols and then expects a blank. Anything shorter or longer records ✗ and halts.",
    "2. State code": "Reads the two leading digits; the first digit selects a state, whose allowed second digits are the valid codes 01-38, 97, 99.",
    "3. PAN structure": "States pan1-pan12 skip positions 1-2, then require 5 uppercase letters, 4 digits and 1 uppercase letter.",
    "4. Entity number": "States ent1-ent13 skip 12 symbols, then require position 13 to be 1-9 or A-Z (not 0).",
    "5. Default character": "States def1-def14 skip 13 symbols, then require position 14 to be Z.",
    "Verdict recording": "Shared gadgets: walk left to '<', append ✓/✗ to the verdict stack, and return to the start of the next pass.",
    "Final decision": "Walks over the verdict cells: accepts only if every one is ✓.",
}

PHASE_ORDER: Tuple[str, ...] = (
    "Setup", "1. Length", "2. State code", "3. PAN structure", "4. Entity number",
    "5. Default character", "Verdict recording", "Final decision",
)


@dataclass(frozen=True)
class GstinSpec:
    states: Tuple[str, ...]
    rules: Mapping[Tuple[str, str], Rule]
    phases: Mapping[str, str]


def build_gstin_spec() -> GstinSpec:
    states: List[str] = []
    phases: Dict[str, str] = {}
    rules: Dict[Tuple[str, str], Rule] = {}

    def declare(phase: str, names: List[str]) -> None:
        for n in names:
            states.append(n)
            phases[n] = phase

    def rule(state: str, read: str, nxt: str, write: str, move: str) -> None:
        key = (state, read)
        assert key not in rules, f"duplicate rule for {key}"
        rules[key] = (nxt, write, move)

    first_digits = sorted({code[0] for code in STATE_CODES})
    second_digits = {d: {code[1] for code in STATE_CODES if code[0] == d} for d in first_digits}

    declare("Setup", ["q0", "init1", "init2", "init3"])
    declare("1. Length", [f"len{i}" for i in range(1, 17)])
    declare("2. State code", ["sc1"] + [f"sc2_{d}" for d in first_digits])
    declare("3. PAN structure", [f"pan{i}" for i in range(1, 13)])
    declare("4. Entity number", [f"ent{i}" for i in range(1, 14)])
    declare("5. Default character", [f"def{i}" for i in range(1, 15)])
    declare("Verdict recording",
            ["back_ok", "back_bad"]
            + [f"w{k}_{t}" for k in range(5) for t in ("ok", "bad")]
            + [n for k in range(4) for n in (f"ret{k}", f"ret{k}b")])
    declare("Final decision", ["agg", "q_accept", "q_reject"])

    # ------------------------------------------------------------- setup
    # Move two cells left of the input, write '<' and '$', come back to cell 0.
    for c in SIGMA + (BLANK,):
        rule("q0", c, "init1", c, "L")          # works for empty input too
    rule("init1", BLANK, "init2", BLANK, "L")
    rule("init2", BLANK, "init3", LEFT_MARK, "R")
    rule("init3", BLANK, "len1", ACC_EMPTY, "R")

    # ------------------------------------------------- pass 1: length
    for i in range(1, 16):
        for c in SIGMA:
            rule(f"len{i}", c, f"len{i + 1}", c, "R")
        rule(f"len{i}", BLANK, "back_bad", BLANK, "L")        # too short
    rule("len16", BLANK, "back_ok", BLANK, "L")                # exactly 15
    for c in SIGMA:
        rule("len16", c, "back_bad", c, "L")                   # too long

    # --------------------------------------------- pass 2: state code
    for c in SIGMA:
        if c in first_digits:
            rule("sc1", c, f"sc2_{c}", c, "R")
        else:
            rule("sc1", c, "back_bad", c, "L")
    for d in first_digits:
        for c in SIGMA:
            rule(f"sc2_{d}", c, "back_ok" if c in second_digits[d] else "back_bad", c, "L")

    # ------------------------------------------------ pass 3: PAN
    def pan_allowed(i: int):
        if i <= 2:
            return set(SIGMA)              # state-code positions: skipped here
        if i <= 7:
            return set(LETTERS)            # PAN chars 1-5
        if i <= 11:
            return set(DIGITS)             # PAN chars 6-9
        return set(LETTERS)                # PAN char 10

    for i in range(1, 13):
        last = i == 12
        for c in SIGMA:
            if c in pan_allowed(i):
                rule(f"pan{i}", c, "back_ok" if last else f"pan{i + 1}", c, "L" if last else "R")
            else:
                rule(f"pan{i}", c, "back_bad", c, "L")

    # ---------------------------------------------- pass 4: entity
    for i in range(1, 13):
        for c in SIGMA:
            rule(f"ent{i}", c, f"ent{i + 1}", c, "R")
    for c in SIGMA:
        rule("ent13", c, "back_ok" if c != "0" else "back_bad", c, "L")

    # --------------------------------------------- pass 5: default Z
    for i in range(1, 14):
        for c in SIGMA:
            rule(f"def{i}", c, f"def{i + 1}", c, "R")
    for c in SIGMA:
        rule("def14", c, "back_ok" if c == "Z" else "back_bad", c, "L")

    # ------------------------------------------ verdict recording gadgets
    for t, sym in (("ok", OK), ("bad", BAD)):
        b = f"back_{t}"
        for c in SIGMA + (ACC_EMPTY, DONE):
            rule(b, c, b, c, "L")                                # walk left to '<'
        rule(b, LEFT_MARK, f"w0_{t}", LEFT_MARK, "L")
        for k in range(5):                                       # find first free verdict cell
            w = f"w{k}_{t}"
            if k < 4:
                for v in (OK, BAD):
                    rule(w, v, f"w{k + 1}_{t}", v, "L")
            if k == 0:
                target = "ret0" if t == "ok" else "q_reject"     # length failure halts
            elif k < 4:
                target = f"ret{k}"
            else:
                target = "agg" if t == "ok" else "q_reject"
            rule(w, BLANK, target, sym, "R")
    next_start = ["sc1", "pan1", "ent1", "def1"]
    for k in range(4):
        r, rb = f"ret{k}", f"ret{k}b"
        for v in (OK, BAD):
            rule(r, v, r, v, "R")
        rule(r, LEFT_MARK, rb, LEFT_MARK, "R")
        rule(rb, ACC_EMPTY, next_start[k], ACC_EMPTY, "R")

    # ------------------------------------------------ final decision
    rule("agg", OK, "agg", OK, "R")
    rule("agg", BAD, "q_reject", BAD, "R")
    rule("agg", LEFT_MARK, "q_accept", LEFT_MARK, "R")

    return GstinSpec(tuple(states), rules, phases)
