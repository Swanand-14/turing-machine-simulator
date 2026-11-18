"""Tests for the Binary Palindrome Turing Machine (independent of Streamlit).

The oracle `is_palindrome` is used only here, never by the simulator.
"""

import unittest

from tests.test_machines import BIG_LIMIT, LOOPER, all_strings, run_machine
from tm import PAL_MACHINE, Status, TuringMachine


def is_palindrome(s: str) -> bool:
    return s == s[::-1]


class PalindromeExampleTests(unittest.TestCase):
    ACCEPT = ["", "0", "1", "00", "11", "101", "1001", "0110", "01010"]
    REJECT = ["01", "10", "100", "1101", "0010"]

    def test_accepted_examples(self):
        for s in self.ACCEPT:
            tm = run_machine(PAL_MACHINE, s)
            self.assertEqual(tm.status, Status.ACCEPTED, repr(s))
            self.assertTrue(tm.halted_normally)

    def test_rejected_examples(self):
        for s in self.REJECT:
            self.assertEqual(run_machine(PAL_MACHINE, s).status, Status.REJECTED, s)

    def test_empty_string_is_accepted_by_an_actual_transition(self):
        tm = run_machine(PAL_MACHINE, "")
        self.assertEqual(tm.status, Status.ACCEPTED)
        self.assertEqual([(r.state_before, r.read, r.state_after) for r in tm.history],
                         [("q0", "B", "q_accept")])

    def test_single_symbols_even_and_odd_lengths(self):
        for s in ("0", "1", "00", "11", "000", "010", "101", "0110", "10101"):
            self.assertEqual(run_machine(PAL_MACHINE, s).status, Status.ACCEPTED, s)
        for s in ("01", "001", "0001", "0111", "1000"):
            self.assertEqual(run_machine(PAL_MACHINE, s).status, Status.REJECTED, s)

    def test_invalid_alphabet(self):
        for s in ("012", "0a1", "0 1", "X", "0B1", "2"):
            tm = TuringMachine(PAL_MACHINE, s)
            self.assertEqual(tm.status, Status.INVALID_INPUT, s)
            self.assertEqual(tm.run(), Status.INVALID_INPUT)
            self.assertEqual(tm.steps, 0)

    def test_known_trace_for_101(self):
        tm = run_machine(PAL_MACHINE, "101")
        got = [(r.state_before, r.read, r.state_after, r.write, r.move) for r in tm.history]
        self.assertEqual(got, [
            ("q0", "1", "q2", "X", "R"),
            ("q2", "0", "q2", "0", "R"),
            ("q2", "1", "q2", "1", "R"),
            ("q2", "B", "q4", "B", "L"),
            ("q4", "1", "q5", "X", "L"),
            ("q5", "0", "q5", "0", "L"),
            ("q5", "X", "q0", "X", "R"),
            ("q0", "0", "q1", "X", "R"),
            ("q1", "X", "q3", "X", "L"),
            ("q3", "X", "q_accept", "X", "R"),
        ])
        self.assertEqual(tm.get_configuration().cells, ((0, "X"), (1, "X"), (2, "X")))


class PalindromeOracleTests(unittest.TestCase):
    def test_all_binary_strings_up_to_length_13(self):
        for s in all_strings("01", 13):
            tm = run_machine(PAL_MACHINE, s)
            expected = Status.ACCEPTED if is_palindrome(s) else Status.REJECTED
            self.assertEqual(tm.status, expected, repr(s))
            self.assertTrue(tm.halted_normally)

    def test_longer_palindromes_and_single_edits(self):
        bases = ["0" * 25, "1" * 24, "01" * 12 + "0", "0110" * 6, "1" + "0" * 20 + "1"]
        for b in bases:
            self.assertTrue(is_palindrome(b))
            variants = {b}
            for i in range(len(b)):
                variants.add(b[:i] + ("1" if b[i] == "0" else "0") + b[i + 1:])
                variants.add(b[:i] + b[i + 1:])
            for v in variants:
                expected = Status.ACCEPTED if is_palindrome(v) else Status.REJECTED
                self.assertEqual(run_machine(PAL_MACHINE, v).status, expected, v)

    def test_every_valid_input_halts_in_accept_or_reject_state(self):
        for s in all_strings("01", 9):
            tm = run_machine(PAL_MACHINE, s)
            self.assertIn(tm.state, ("q_accept", "q_reject"))


class PalindromeEngineTests(unittest.TestCase):
    def test_step_by_step_equals_run(self):
        for s in ("", "0", "101", "1001", "0110", "01", "100", "1101", "01010"):
            full = run_machine(PAL_MACHINE, s)
            stepper = TuringMachine(PAL_MACHINE, s)
            guard = 0
            while not stepper.halted:
                self.assertIsNotNone(stepper.step())
                guard += 1
                self.assertLess(guard, BIG_LIMIT)
            self.assertEqual(stepper.get_configuration(), full.get_configuration(), s)
            self.assertEqual(stepper.history, full.history, s)

    def test_reset_restores_initial_configuration(self):
        fresh = TuringMachine(PAL_MACHINE, "1001").get_configuration()
        tm = TuringMachine(PAL_MACHINE, "1001")
        for _ in range(6):
            tm.step()
        self.assertNotEqual(tm.get_configuration(), fresh)
        tm.reset()
        self.assertEqual(tm.get_configuration(), fresh)
        self.assertEqual(tm.history, ())

    def test_history_replays_on_an_independent_tape(self):
        for s in ("", "0", "1001", "01010", "1101", "0010"):
            tm = run_machine(PAL_MACHINE, s)
            cells = dict(enumerate(s))
            head, state = 0, "q0"
            for i, r in enumerate(tm.history, 1):
                self.assertEqual((r.step, r.state_before, r.head_before), (i, state, head))
                self.assertEqual(r.read, cells.get(head, "B"))
                self.assertEqual(PAL_MACHINE.transitions[(r.state_before, r.read)],
                                 (r.state_after, r.write, r.move))
                cells[head] = r.write
                head += 1 if r.move == "R" else -1
                state = r.state_after
            self.assertEqual(state, tm.state)
            self.assertEqual(head, tm.tape.head)

    def test_head_moves_left_and_into_blank_cells(self):
        tm = run_machine(PAL_MACHINE, "1001")
        moves = {r.move for r in tm.history}
        self.assertEqual(moves, {"L", "R"})
        self.assertTrue(any(r.read == "B" for r in tm.history))      # read a never-written cell
        self.assertGreater(max(r.head_after for r in tm.history), 3)  # moved past the input

    def test_step_limit_gives_timeout_not_rejection(self):
        tm = TuringMachine(PAL_MACHINE, "0110")
        self.assertEqual(tm.run(max_steps=4), Status.TIMEOUT)
        self.assertEqual((tm.steps, tm.halted), (4, False))
        self.assertNotEqual(tm.status, Status.REJECTED)
        self.assertEqual(tm.run(), Status.ACCEPTED)

    def test_definition_is_total_and_uses_the_shared_engine(self):
        self.assertEqual(PAL_MACHINE.missing_transitions(), [])
        self.assertIs(type(TuringMachine(PAL_MACHINE)), type(TuringMachine(LOOPER)))


if __name__ == "__main__":
    unittest.main()
