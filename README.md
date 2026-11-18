# Interactive Turing Machine Simulator

A Streamlit application that executes real, explicit-transition Turing Machines for four languages/validators and shows the tape, head, state, transition history, state diagram and transition table.

All machines run on **one** reusable engine. The ACCEPT/REJECT result is produced only by the machine reaching `q_accept` or `q_reject`. There is no regular expression or Python membership check anywhere in the simulator (membership oracles exist only in `tests/`).

## Languages

| | Language | Σ |
|---|---|---|
| Machine A | L1 = { 0ⁿ1ⁿ \| n ≥ 1 } | {0, 1} |
| Machine B | L2 = { 0ⁿ1ⁿ2ⁿ \| n ≥ 1 } | {0, 1, 2} |
| Machine C | L3 = { w ∈ {0,1}\* \| w = wᴿ } (binary palindromes, empty string included) | {0, 1} |
| Machine D | GSTIN format validator (15 characters) | {0-9, A-Z} |

## Formalism

Each machine is a deterministic single-tape TM **M = (Q, Σ, Γ, δ, q₀, B, F)**:

- **Q**: finite set of states, **Σ**: input alphabet, **Γ**: tape alphabet (Σ ⊂ Γ), **B**: blank (B ∈ Γ, B ∉ Σ), **q₀**: initial state.
- **δ**: (state, read) → (next state, write, direction), direction ∈ {L, R}.
- **F = {q_accept}**. `q_reject` is an explicit rejecting halt state.

Conventions (applied identically to both machines):

1. Entering `q_accept` halts with **ACCEPTED**; entering `q_reject` halts with **REJECTED**. Neither has outgoing transitions.
2. δ is **total** on every non-halting state × Γ. Each "wrong symbol" case is an explicit transition `(q, a) → (q_reject, a, R)` stored in δ and shown in the table and diagram.
3. If the engine ever finds no rule it reports **UNDEFINED TRANSITION**, never ACCEPT or REJECT. (The tests confirm this never happens for the two machines.)
4. Input symbols outside Σ (including `B`, `X`, `Y`, `Z`, spaces) give **INVALID INPUT**; nothing is executed.
5. The **empty string** is valid input. The machine reads `B` in `q0` and rejects in one step, since n ≥ 1 is required.
6. Hitting the step limit gives **TIMEOUT**, never REJECTED. The machine has not halted and can be resumed.

### Machine A: L1 = { 0ⁿ1ⁿ | n ≥ 1 }

Γ = {0, 1, X, Y, B}. **Marking:** X = matched 0, Y = matched 1. Each round marks the leftmost unmarked 0 as X, scans right and marks the first unmarked 1 as Y, then returns to the X. When `q0` sees a Y instead of a 0, all zeros are matched and `q3` checks that only Y's remain before the blank.

| State | Read | Write | Move | Next |
|---|---|---|---|---|
| q0 | 0 | X | R | q1 |
| q0 | Y | Y | R | q3 |
| q1 | 0 | 0 | R | q1 |
| q1 | Y | Y | R | q1 |
| q1 | 1 | Y | L | q2 |
| q2 | 0 | 0 | L | q2 |
| q2 | Y | Y | L | q2 |
| q2 | X | X | R | q0 |
| q3 | Y | Y | R | q3 |
| q3 | B | B | R | q_accept |

Every other (state, symbol) pair for q0–q3 goes to `q_reject` (symbol unchanged, move R).

### Machine B: L2 = { 0ⁿ1ⁿ2ⁿ | n ≥ 1 }

Γ = {0, 1, 2, X, Y, Z, B}. **Marking:** X = matched 0, Y = matched 1, Z = matched 2. Each round marks one 0 (`q0`), the next unmarked 1 to its right (`q1`), and the next unmarked 2 to the right of that (`q2`), then returns left to the X (`q3`). When `q0` meets a Y, no 0 is left and `q4`/`q5` verify that the rest of the tape is exactly Y\* Z⁺ then blank.

| State | Read | Write | Move | Next |
|---|---|---|---|---|
| q0 | 0 | X | R | q1 |
| q0 | Y | Y | R | q4 |
| q1 | 0 | 0 | R | q1 |
| q1 | Y | Y | R | q1 |
| q1 | 1 | Y | R | q2 |
| q2 | 1 | 1 | R | q2 |
| q2 | Z | Z | R | q2 |
| q2 | 2 | Z | L | q3 |
| q3 | 0, 1, Y, Z | (same) | L | q3 |
| q3 | X | X | R | q0 |
| q4 | Y | Y | R | q4 |
| q4 | Z | Z | R | q5 |
| q5 | Z | Z | R | q5 |
| q5 | B | B | R | q_accept |

Every other (state, symbol) pair for q0–q5 goes to `q_reject`.

### Machine C: binary palindromes, L3 = { w ∈ {0,1}* | w = wᴿ }

Γ = {0, 1, X, B}. **Marking:** X marks every processed cell, at both ends. Each round `q0` reads the leftmost unprocessed symbol, **remembers it in the state** (`q1` = remembered 0, `q2` = remembered 1) and marks it X. The head runs right to the end of the unprocessed part, steps back onto the rightmost unprocessed symbol, and `q3`/`q4` compare it with the remembered symbol. A match is marked X and `q5` returns left to the last mark; a mismatch goes to `q_reject`. If the head steps back onto its own mark there is nothing left to compare (odd-length middle) and the machine accepts. If `q0` meets an X or the blank, every symbol has been paired and it accepts. The empty string is accepted in one step (`q0` reads B).

| State | Read | Write | Move | Next |
|---|---|---|---|---|
| q0 | 0 | X | R | q1 |
| q0 | 1 | X | R | q2 |
| q0 | X or B | (same) | R | q_accept |
| q1 | 0, 1 | (same) | R | q1 |
| q1 | X or B | (same) | L | q3 |
| q2 | 0, 1 | (same) | R | q2 |
| q2 | X or B | (same) | L | q4 |
| q3 | 0 | X | L | q5 |
| q3 | X | X | R | q_accept |
| q3 | 1 | 1 | R | q_reject (mismatch) |
| q4 | 1 | X | L | q5 |
| q4 | X | X | R | q_accept |
| q4 | 0 | 0 | R | q_reject (mismatch) |
| q5 | 0, 1 | (same) | L | q5 |
| q5 | X | X | R | q0 |

### Machine D: GSTIN validator

Input alphabet Σ = {0-9, A-Z}. The blank symbol is `_` (not `B`, because B is a letter of the alphabet). The machine accepts ("VALID GSTIN") only if the input has the right length, a valid state code, a PAN-shaped middle, a valid entity character, and the letter Z in position 14. Position 15 can be any digit or uppercase letter.

**Tape layout.** The input occupies positions 0-14. The machine itself writes a left sentinel `<` at position -2 and an unused `$` cell at position -1, and it appends one verdict cell (✓ or ✗) per check at positions -3 (length), -4 (state code), -5 (PAN), -6 (entity), -7 (default Z). The UI's "Validation checks" table simply reads those cells from the tape.

**Passes.** Each check is a separate group of states (a "phase") that reads the input without modifying it, records ✓/✗, and returns to the left end:

| Phase | States | What the transitions do |
|---|---|---|
| Setup | 4 | write `<` and `$` (empty accumulator) left of the input |
| 1 Length | 16 | a chain `len1..len16` consumes exactly 15 symbols and then needs a blank |
| 2 State code | 6 | first digit selects a state, whose allowed second digits are exactly the valid codes |
| 3 PAN | 12 | skip 2, then 5 letters, 4 digits, 1 letter |
| 4 Entity | 13 | skip 12, then position 13 must be 1-9 or A-Z (not 0) |
| 5 Default | 14 | skip 13, then position 14 must be Z |
| Verdict recording | 20 | shared gadgets that walk left, append ✓/✗, and return |
| Final | 3 | accept iff every verdict cell is ✓ |

If the length check fails the machine records ✗ and halts; the other checks are tied to positions and are shown as "Not evaluated". Otherwise all four remaining checks run independently of each other, so one malformed field does not hide a second one.

**State codes** accepted: 01-38, 97, 99. Codes 25 (Daman and Diu) and 28 (Andhra Pradesh before division) are legacy codes that are no longer issued but remain on older registrations, so they are accepted. This list is encoded purely in the transition rules of `sc1`/`sc2_*` (see `STATE_CODES` in `tm/gstin_machine.py`).

#### What is and is not done by Turing Machine transitions

**Done entirely by explicit TM transitions (the engine only looks up and applies them):** the length check, the state-code check, the PAN structure check, the entity-number check, the default-character check, recording the five verdicts, and the final accept/reject decision.

**Not done by the TM, and where this matters:**

- **Alphabet validation.** Symbols outside 0-9 and A-Z (lowercase letters, spaces, hyphens, anything else) are rejected *before* execution as INVALID INPUT by the engine's Σ check (the same convention as every machine here). The TM itself only ever sees uppercase letters and digits.
- **The simulator** (`tm/engine.py`) is a generic Turing Machine interpreter. It contains no GSTIN logic.
- **The "Validation checks" table** in the UI only reads the ✓/✗ cells the machine wrote; it computes nothing.
- **The tests** use independent Python oracles (and, if installed, python-stdnum's Luhn mod-36) to judge the machine. Those oracles are never used by the simulator.

**Not checked by this machine at all:** whether the GSTIN check digit is correct; whether the GSTIN is registered or active (that needs the GST portal); the 4th PAN character (holder type); that the PAN itself exists. **A VALID GSTIN result means only that the format is correct.**

**Practical notes.** δ has about 4,300 transitions (36 input symbols × about 100 states), and runs take up to roughly 10,000 steps (the GSTIN default step limit is 50,000). The UI therefore offers a compact (grouped) table view and draws the diagram one phase at a time; the compact table is rebuilt from the same dictionary and a test expands it back to check that it matches every transition. About 1,450 transitions exist only to make δ total for (state, symbol) pairs the design never reaches; they are flagged in the table and hidden in the diagram, and a test confirms they are never executed.

## Architecture

```
turing-machine-simulator/
├── app.py                      Streamlit UI (display + button wiring only)
├── requirements.txt
├── README.md
├── tm/
│   ├── __init__.py
│   ├── tape.py                 two-way infinite tape, dict {position: symbol}, head position
│   ├── engine.py               TuringMachine: initialize / step / run / reset / get_configuration
│   ├── machine_definitions.py  MachineDefinition (validated 7-tuple) + the four machines
│   ├── gstin_machine.py        builder for the GSTIN rule table (pure data) and its documentation
│   └── visualization.py        tape window/HTML, Graphviz DOT (full, compact, per-phase), grouped table
└── tests/
    ├── test_machines.py                 engine, tape, L1 and L2 correctness
    ├── test_palindrome.py               palindrome machine
    ├── test_gstin.py                    GSTIN machine (sourced examples, oracles)
    ├── test_visualization_and_app.py    tape window, diagram, Streamlit AppTest smoke tests
    └── test_new_machines_ui.py          new machines in the UI, grouped table, phase diagrams
```

## How the engine works

- **Tape:** a dictionary `position → symbol`. Unwritten positions read as `B`, so the head can move to any integer position, including negative ones. Writing `B` removes the cell. The head position is a separate integer.
- **`initialize(s)`:** validates `s ⊆ Σ*`, loads it at positions 0…n−1, sets the state to q₀ and clears the history.
- **`step()`:** looks up `δ[(state, symbol under head)]`, writes, moves, updates the state, appends one `TransitionRecord`, then checks for a halting state. After halting it does nothing.
- **`run(max_steps)`:** calls `step()` until the machine halts or `max_steps` more transitions were executed (then status is TIMEOUT).
- **`reset()`:** re-initializes with the same input. **`get_configuration()`:** immutable snapshot (step, state, head, non-blank cells, status).
- The Streamlit app keeps one engine in `st.session_state`, rebuilt whenever the language or input text changes, so stale state is never reused. The history table is rendered from the engine, so reruns cannot duplicate rows.

## Install and run

Requires Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The state diagram uses Streamlit's built-in Graphviz rendering, so no system Graphviz installation is needed. The GSTIN machine is drawn one phase at a time (choose a view above the diagram).

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

Uses only the standard library. Streamlit tests are skipped if Streamlit is not installed. The GSTIN tests compare the machine against an independent format-regex validator. The tests include: all examples from the specification; the empty string; invalid alphabets; ordering and count errors; exhaustive comparison against independent oracles (all binary strings up to length 12 for L1, all strings over {0,1,2} up to length 8 for L2, plus larger members and every single insertion/deletion/substitution/swap of them); head movement left of the origin and into blank cells; step-by-step equals full run; reset; independent replay of the history; step-limit behaviour; undefined transitions.

## Example inputs

| Language | Input | Result |
|---|---|---|
| L1 | 01, 0011, 000111 | ACCEPTED |
| L1 | 001, 011, 0101, 111000, (empty) | REJECTED |
| L1 | 012 | INVALID INPUT |
| L2 | 012, 001122, 000111222 | ACCEPTED |
| L2 | 00112, 001222, 0122, 102, 00011222, (empty) | REJECTED |
| L2 | 0123 | INVALID INPUT |
| L3 | (empty), 0, 1, 00, 11, 101, 1001, 0110, 01010 | ACCEPTED |
| L3 | 01, 10, 100, 1101, 0010 | REJECTED |
| GSTIN | 27AAPFU0939F1AV (last character may be any alphanumeric) | VALID GSTIN |
| GSTIN | 27AAPFU0939F1Z (14 characters) | INVALID GSTIN (length ✗, others not evaluated) |
| GSTIN | 27aapfu0939f1zv (lowercase) | INVALID INPUT |

## Known limitations

- Only these four machines are provided. Machine definitions are fixed in code and cannot be edited in the UI (by design).
- Each machine decides only its own language/format, over its own Σ. The GSTIN machine does not verify registration status or the PAN holder-type letter. A string using a symbol outside Σ is reported as INVALID INPUT, not as "not in the language".
- Both machines halt on every valid input, but the step limit still exists for display safety. Running time is O(n²) transitions, so very long inputs take many steps.
- The tape view shows at most 25 cells around the head; hidden cells are indicated with `…n`.
- The diagram's "group transitions into q_reject" option is a display choice only; the full table always lists every transition.
