"""Automated tests for the Turing Machine simulator (independent of Streamlit).

The membership oracles below are used ONLY here, to check the simulator.
The simulator itself never calls them.
"""

import itertools
import unittest

from tm import (
    L1_MACHINE,
    L2_MACHINE,
    MachineDefinition,
    Status,
    Tape,
    TuringMachine,
)

BIG_LIMIT = 100_000


# ----------------------------------------------------------------- oracles
def in_L1(s: str) -> bool:
    """0^n 1^n with n >= 1."""
    n = len(s) // 2
    return len(s) % 2 == 0 and n >= 1 and s == "0" * n + "1" * n


def in_L2(s: str) -> bool:
    """0^n 1^n 2^n with n >= 1."""
    n = len(s) // 3
    return len(s) % 3 == 0 and n >= 1 and s == "0" * n + "1" * n + "2" * n


def run_machine(defn: MachineDefinition, s: str, limit: int = BIG_LIMIT) -> TuringMachine:
    tm = TuringMachine(defn, s)
    tm.run(max_steps=limit)
    return tm


def all_strings(alphabet: str, max_len: int):
    for n in range(max_len + 1):
        for tup in itertools.product(alphabet, repeat=n):
            yield "".join(tup)


# --------------------------------------------------------- custom machines
def make_machine(transitions, states, sigma, gamma, accept=("acc",), reject=("rej",)):
    return MachineDefinition(
        key="custom",
        states=tuple(states),
        input_alphabet=tuple(sigma),
        tape_alphabet=tuple(gamma),
        transitions=transitions,
        initial_state="s0",
        blank="B",
        accept_states=tuple(accept),
        reject_states=tuple(reject),
    )


# Walks left of the starting cell into never-written blank cells, then returns.
LEFT_WALKER = make_machine(
    {
        ("s0", "0"): ("s1", "1", "L"),   # head 0 -> -1
        ("s1", "B"): ("s2", "1", "L"),   # head -1 -> -2 (blank cell)
        ("s2", "B"): ("s3", "1", "R"),   # head -2 -> -1
        ("s3", "1"): ("s4", "1", "R"),   # head -1 -> 0
        ("s4", "1"): ("acc", "1", "R"),  # head 0 -> 1
    },
    states=("s0", "s1", "s2", "s3", "s4", "acc", "rej"),
    sigma="0",
    gamma="01B",
)

# Never halts on any input.
LOOPER = make_machine(
    {("s0", "0"): ("s0", "0", "R"), ("s0", "B"): ("s0", "B", "R")},
    states=("s0", "acc", "rej"),
    sigma="0",
    gamma="0B",
)

# Deliberately incomplete: no rule for (s0, B).
INCOMPLETE = make_machine(
    {("s0", "0"): ("acc", "0", "R")},
    states=("s0", "acc", "rej"),
    sigma="0",
    gamma="0B",
)


# ------------------------------------------------------------------- tests
class TapeTests(unittest.TestCase):
    def test_blank_default_and_negative_positions(self):
        t = Tape("B", "01")
        self.assertEqual(t.read(), "0")
        t.move("L")
        self.assertEqual(t.head, -1)
        self.assertEqual(t.read(), "B")
        t.write("X")
        self.assertEqual(t.cell(-1), "X")
        self.assertEqual(t.snapshot(), ((-1, "X"), (0, "0"), (1, "1")))
        self.assertEqual(t.bounds(), (-1, 1))

    def test_writing_blank_erases(self):
        t = Tape("B", "0")
        t.write("B")
        self.assertEqual(t.snapshot(), ())

    def test_bad_direction_rejected(self):
        with self.assertRaises(ValueError):
            Tape("B", "0").move("S")


class DefinitionTests(unittest.TestCase):
    def test_both_machines_are_total_on_non_halting_states(self):
        self.assertEqual(L1_MACHINE.missing_transitions(), [])
        self.assertEqual(L2_MACHINE.missing_transitions(), [])

    def test_halting_states_have_no_outgoing_transitions(self):
        for d in (L1_MACHINE, L2_MACHINE):
            for (q, _a) in d.transitions:
                self.assertNotIn(q, d.halting_states)

    def test_blank_not_in_input_alphabet(self):
        for d in (L1_MACHINE, L2_MACHINE):
            self.assertNotIn(d.blank, d.input_alphabet)
            self.assertIn(d.blank, d.tape_alphabet)

    def test_invalid_definitions_raise(self):
        with self.assertRaises(ValueError):   # outgoing transition from halting state
            make_machine({("acc", "0"): ("s0", "0", "R")}, ("s0", "acc", "rej"), "0", "0B")
        with self.assertRaises(ValueError):   # direction other than L/R
            make_machine({("s0", "0"): ("acc", "0", "S")}, ("s0", "acc", "rej"), "0", "0B")
        with self.assertRaises(ValueError):   # blank inside the input alphabet
            make_machine({}, ("s0", "acc", "rej"), "0B", "0B")
        with self.assertRaises(ValueError):   # symbol outside Γ
            make_machine({("s0", "0"): ("acc", "Q", "R")}, ("s0", "acc", "rej"), "0", "0B")

    def test_sorted_transitions_cover_every_rule(self):
        for d in (L1_MACHINE, L2_MACHINE):
            rows = d.sorted_transitions()
            self.assertEqual(len(rows), len(d.transitions))
            for r in rows:
                self.assertEqual(d.transitions[(r.state, r.read)], (r.next_state, r.write, r.move))


class ExampleTests(unittest.TestCase):
    L1_ACCEPT = ["01", "0011", "000111"]
    L1_REJECT = ["001", "011", "0101", "111000", "", "0", "1", "10", "00111", "0111", "1100"]
    L2_ACCEPT = ["012", "001122", "000111222"]
    L2_REJECT = ["00112", "001222", "0122", "102", "00011222", "", "0", "01", "0011",
                 "012012", "021", "210", "0112", "011222", "002211"]

    def test_L1_examples(self):
        for s in self.L1_ACCEPT:
            self.assertEqual(run_machine(L1_MACHINE, s).status, Status.ACCEPTED, s)
        for s in self.L1_REJECT:
            self.assertEqual(run_machine(L1_MACHINE, s).status, Status.REJECTED, repr(s))

    def test_L2_examples(self):
        for s in self.L2_ACCEPT:
            self.assertEqual(run_machine(L2_MACHINE, s).status, Status.ACCEPTED, s)
        for s in self.L2_REJECT:
            self.assertEqual(run_machine(L2_MACHINE, s).status, Status.REJECTED, repr(s))

    def test_empty_string_is_valid_input_and_rejected(self):
        for d in (L1_MACHINE, L2_MACHINE):
            tm = TuringMachine(d, "")
            self.assertNotEqual(tm.status, Status.INVALID_INPUT)
            tm.run()
            self.assertEqual(tm.status, Status.REJECTED)
            self.assertEqual(tm.steps, 1)         # q0 reads B -> q_reject
            self.assertTrue(tm.halted_normally)

    def test_invalid_alphabet(self):
        cases = [
            (L1_MACHINE, "012"), (L1_MACHINE, "01a"), (L1_MACHINE, "0 1"),
            (L1_MACHINE, "0B1"), (L1_MACHINE, "0X1"), (L1_MACHINE, "01Y"),
            (L2_MACHINE, "0123"), (L2_MACHINE, "01 2"), (L2_MACHINE, "0B12"),
            (L2_MACHINE, "XYZ"), (L2_MACHINE, "01\n2"),
        ]
        for d, s in cases:
            tm = TuringMachine(d, s)
            self.assertEqual(tm.status, Status.INVALID_INPUT, s)
            self.assertTrue(tm.invalid_symbols)
            self.assertEqual(tm.run(), Status.INVALID_INPUT)
            self.assertEqual(tm.steps, 0)
            self.assertIsNone(tm.step())
            self.assertFalse(tm.halted_normally)

    def test_valid_L1_strings_are_invalid_for_nothing_but_L2_is_distinct(self):
        # "012" is outside Σ of L1 (INVALID INPUT) but in L2.
        self.assertEqual(TuringMachine(L1_MACHINE, "012").status, Status.INVALID_INPUT)
        self.assertEqual(run_machine(L2_MACHINE, "012").status, Status.ACCEPTED)


class ExhaustiveOracleTests(unittest.TestCase):
    def test_L1_all_binary_strings_up_to_length_12(self):
        for s in all_strings("01", 12):
            tm = run_machine(L1_MACHINE, s)
            expected = Status.ACCEPTED if in_L1(s) else Status.REJECTED
            self.assertEqual(tm.status, expected, repr(s))
            self.assertTrue(tm.halted_normally)

    def test_L2_all_strings_over_012_up_to_length_8(self):
        for s in all_strings("012", 8):
            tm = run_machine(L2_MACHINE, s)
            expected = Status.ACCEPTED if in_L2(s) else Status.REJECTED
            self.assertEqual(tm.status, expected, repr(s))
            self.assertTrue(tm.halted_normally)

    def test_L1_larger_members_and_single_edit_mutations(self):
        self._check_mutations(L1_MACHINE, in_L1, lambda n: "0" * n + "1" * n, "01", 20)

    def test_L2_larger_members_and_single_edit_mutations(self):
        self._check_mutations(L2_MACHINE, in_L2, lambda n: "0" * n + "1" * n + "2" * n, "012", 12)

    def _check_mutations(self, defn, oracle, member, alphabet, max_n):
        for n in range(1, max_n + 1):
            base = member(n)
            self.assertTrue(oracle(base))
            self.assertEqual(run_machine(defn, base).status, Status.ACCEPTED, base)
            variants = set()
            for i in range(len(base) + 1):
                for c in alphabet:
                    variants.add(base[:i] + c + base[i:])          # insertion
            for i in range(len(base)):
                variants.add(base[:i] + base[i + 1:])               # deletion
                for c in alphabet:
                    variants.add(base[:i] + c + base[i + 1:])       # substitution
                if i + 1 < len(base):                               # adjacent swap
                    variants.add(base[:i] + base[i + 1] + base[i] + base[i + 2:])
            for v in variants:
                expected = Status.ACCEPTED if oracle(v) else Status.REJECTED
                self.assertEqual(run_machine(defn, v).status, expected, repr(v))

    def test_no_undefined_transition_ever_occurs(self):
        for d, alphabet, n in ((L1_MACHINE, "01", 9), (L2_MACHINE, "012", 7)):
            for s in all_strings(alphabet, n):
                self.assertNotEqual(run_machine(d, s).status, Status.UNDEFINED_TRANSITION, s)


class EngineBehaviourTests(unittest.TestCase):
    def test_head_moves_left_of_start_into_blank_cells(self):
        tm = run_machine(LEFT_WALKER, "0")
        self.assertEqual(tm.status, Status.ACCEPTED)
        cfg = tm.get_configuration()
        self.assertEqual(cfg.span[0], -2)
        self.assertEqual(cfg.cells, ((-2, "1"), (-1, "1"), (0, "1")))
        self.assertEqual(cfg.head, 1)
        self.assertEqual(min(r.head_after for r in tm.history), -2)

    def test_head_reads_uninitialised_blank_cells_to_the_right(self):
        tm = run_machine(L1_MACHINE, "01")
        cfg = tm.get_configuration()
        self.assertEqual(cfg.cells, ((0, "X"), (1, "Y")))
        self.assertEqual(cfg.symbol_at(2), "B")
        self.assertEqual(cfg.head, 3)               # moved past the blank into fresh cells
        self.assertEqual(tm.history[-1].read, "B")

    def test_known_trace_for_01(self):
        tm = run_machine(L1_MACHINE, "01")
        got = [(r.state_before, r.read, r.state_after, r.write, r.move) for r in tm.history]
        self.assertEqual(got, [
            ("q0", "0", "q1", "X", "R"),
            ("q1", "1", "q2", "Y", "L"),
            ("q2", "X", "q0", "X", "R"),
            ("q0", "Y", "q3", "Y", "R"),
            ("q3", "B", "q_accept", "B", "R"),
        ])

    def test_known_final_tape_for_L2(self):
        tm = run_machine(L2_MACHINE, "001122")
        self.assertEqual(tm.status, Status.ACCEPTED)
        self.assertEqual(tm.get_configuration().cells,
                         tuple(enumerate("XXYYZZ")))

    def test_step_by_step_matches_full_run(self):
        samples = [(L1_MACHINE, s) for s in ("", "01", "0011", "001", "0101", "000111", "10")]
        samples += [(L2_MACHINE, s) for s in ("", "012", "001122", "00112", "0122", "000111222", "102")]
        for d, s in samples:
            full = run_machine(d, s)
            stepper = TuringMachine(d, s)
            guard = 0
            while not stepper.halted:
                rec = stepper.step()
                self.assertIsNotNone(rec)
                guard += 1
                self.assertLess(guard, BIG_LIMIT)
            self.assertEqual(stepper.status, full.status, s)
            self.assertEqual(stepper.steps, full.steps, s)
            self.assertEqual(stepper.state, full.state, s)
            self.assertEqual(stepper.get_configuration(), full.get_configuration(), s)
            self.assertEqual(stepper.history, full.history, s)

    def test_step_executes_exactly_one_transition(self):
        tm = TuringMachine(L2_MACHINE, "012")
        for expected in range(1, 6):
            rec = tm.step()
            self.assertEqual(rec.step, expected)
            self.assertEqual(tm.steps, expected)
            self.assertEqual(len(tm.history), expected)

    def test_step_after_halt_is_a_noop(self):
        tm = run_machine(L1_MACHINE, "01")
        before = tm.get_configuration()
        self.assertIsNone(tm.step())
        self.assertEqual(tm.get_configuration(), before)
        self.assertEqual(len(tm.history), before.step)

    def test_reset_restores_initial_configuration(self):
        for d, s in ((L1_MACHINE, "0011"), (L2_MACHINE, "001122"), (L1_MACHINE, "0")):
            fresh = TuringMachine(d, s).get_configuration()
            tm = TuringMachine(d, s)
            tm.step(); tm.step(); tm.step()
            self.assertNotEqual(tm.get_configuration(), fresh)
            tm.reset()
            self.assertEqual(tm.get_configuration(), fresh)
            self.assertEqual(tm.history, ())
            self.assertEqual(tm.status, Status.RUNNING)
            self.assertEqual(tm.input_string, s)
            tm.run()
            tm.reset()
            self.assertEqual(tm.get_configuration(), fresh)

    def test_initialize_replaces_stale_state(self):
        tm = TuringMachine(L1_MACHINE, "0011")
        tm.run()
        tm.initialize("01")
        self.assertEqual(tm.steps, 0)
        self.assertEqual(tm.history, ())
        self.assertEqual(tm.get_configuration().cells, ((0, "0"), (1, "1")))

    def test_history_matches_definition_and_independent_replay(self):
        for d, s in ((L1_MACHINE, "000111"), (L1_MACHINE, "0101"),
                     (L2_MACHINE, "001122"), (L2_MACHINE, "00112"), (L2_MACHINE, "")):
            tm = run_machine(d, s)
            cells = {i: c for i, c in enumerate(s)}        # independent tape replay
            head, state = 0, d.initial_state
            self.assertEqual(len(tm.history), tm.steps)
            for i, rec in enumerate(tm.history, start=1):
                self.assertEqual(rec.step, i)
                self.assertEqual(rec.state_before, state)
                self.assertEqual(rec.head_before, head)
                self.assertEqual(rec.read, cells.get(head, d.blank))
                self.assertEqual(d.transitions[(rec.state_before, rec.read)],
                                 (rec.state_after, rec.write, rec.move))
                cells[head] = rec.write
                head += 1 if rec.move == "R" else -1
                state = rec.state_after
                self.assertEqual(rec.head_after, head)
            self.assertEqual(state, tm.state)
            self.assertEqual(head, tm.tape.head)
            final = {p: c for p, c in cells.items() if c != d.blank}
            self.assertEqual(dict(tm.get_configuration().cells), final)

    def test_next_transition_preview_matches_executed_step(self):
        tm = TuringMachine(L2_MACHINE, "0112")
        while not tm.halted:
            state, read, rule = tm.next_transition()
            rec = tm.step()
            self.assertEqual((rec.state_before, rec.read), (state, read))
            self.assertEqual((rec.state_after, rec.write, rec.move), rule)
        self.assertIsNone(tm.next_transition())

    def test_step_limit_is_timeout_not_rejection(self):
        tm = TuringMachine(L1_MACHINE, "0011")
        self.assertEqual(tm.run(max_steps=3), Status.TIMEOUT)
        self.assertEqual(tm.steps, 3)
        self.assertFalse(tm.halted)
        self.assertFalse(tm.halted_normally)
        self.assertNotEqual(tm.status, Status.REJECTED)
        self.assertNotEqual(tm.status, Status.ACCEPTED)
        # Resuming finishes the same computation as an uninterrupted run.
        self.assertEqual(tm.run(), Status.ACCEPTED)
        self.assertEqual(tm.get_configuration().cells,
                         run_machine(L1_MACHINE, "0011").get_configuration().cells)
        self.assertEqual(tm.steps, run_machine(L1_MACHINE, "0011").steps)

    def test_zero_limit_and_exact_limit(self):
        tm = TuringMachine(L1_MACHINE, "01")
        self.assertEqual(tm.run(max_steps=0), Status.TIMEOUT)
        self.assertEqual(tm.steps, 0)
        n = run_machine(L1_MACHINE, "01").steps            # 5 transitions
        tm = TuringMachine(L1_MACHINE, "01")
        self.assertEqual(tm.run(max_steps=n), Status.ACCEPTED)  # halts exactly at the limit
        with self.assertRaises(ValueError):
            tm.run(max_steps=-1)

    def test_non_halting_machine_times_out(self):
        tm = TuringMachine(LOOPER, "0")
        self.assertEqual(tm.run(max_steps=500), Status.TIMEOUT)
        self.assertEqual(tm.steps, 500)
        self.assertEqual(len(tm.history), 500)
        self.assertNotEqual(tm.status, Status.REJECTED)

    def test_missing_transition_is_reported_separately(self):
        tm = TuringMachine(INCOMPLETE, "")
        self.assertEqual(tm.run(), Status.UNDEFINED_TRANSITION)
        self.assertEqual(tm.steps, 0)
        self.assertIsNotNone(tm.error)
        self.assertFalse(tm.halted_normally)
        self.assertNotIn(tm.status, (Status.ACCEPTED, Status.REJECTED))

    def test_accept_only_in_accepting_state_reject_only_in_rejecting_state(self):
        for d, alphabet, n in ((L1_MACHINE, "01", 8), (L2_MACHINE, "012", 6)):
            for s in all_strings(alphabet, n):
                tm = run_machine(d, s)
                if tm.status == Status.ACCEPTED:
                    self.assertIn(tm.state, d.accept_states)
                else:
                    self.assertIn(tm.state, d.reject_states)

    def test_machines_share_one_engine_class(self):
        self.assertIs(type(TuringMachine(L1_MACHINE)), type(TuringMachine(L2_MACHINE)))


if __name__ == "__main__":
    unittest.main()
