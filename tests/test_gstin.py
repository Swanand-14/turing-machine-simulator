"""Tests for the GSTIN format-validator Turing Machine (independent of Streamlit)."""

import itertools
import random
import re
import unittest

from tests.test_machines import LOOPER, make_machine
from tm import GSTIN_EXPLICIT_TRANSITIONS, GSTIN_MACHINE, Status, TuringMachine

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LIMIT = 100_000
LABELS = list(GSTIN_MACHINE.result_cells)
VALID_STATE_CODES = {f"{n:02d}" for n in range(1, 39)} | {"97", "99"}
GSTIN_FORMAT = re.compile(
    rf"(?:{'|'.join(sorted(VALID_STATE_CODES))})[A-Z]{{5}}[0-9]{{4}}[A-Z][1-9A-Z]Z[0-9A-Z]"
)

KNOWN_VALID = ["27AAPFU0939F1ZV"]


def oracle(s: str):
    """Expected verdicts: True/False per check, None = not evaluated."""
    res = {k: None for k in LABELS}
    res["Length check"] = len(s) == 15
    if len(s) != 15:
        return res
    res["State code check"] = s[:2] in VALID_STATE_CODES
    res["PAN structure check"] = (
        all("A" <= c <= "Z" for c in s[2:7])
        and all("0" <= c <= "9" for c in s[7:11])
        and "A" <= s[11] <= "Z"
    )
    res["Entity number check"] = s[12] in ALPHABET[1:]
    res["Default character check"] = s[13] == "Z"
    return res


def oracle_valid(s: str) -> bool:
    return GSTIN_FORMAT.fullmatch(s) is not None


# ------------------------------------------------------------------ helpers
def run(s: str, limit: int = LIMIT) -> TuringMachine:
    tm = TuringMachine(GSTIN_MACHINE, s)
    tm.run(max_steps=limit)
    return tm


def verdicts(tm: TuringMachine):
    cfg = tm.get_configuration()
    out = {}
    for label, pos in GSTIN_MACHINE.result_cells.items():
        sym = cfg.symbol_at(pos)
        out[label] = (True if sym == GSTIN_MACHINE.pass_symbol
                      else False if sym == GSTIN_MACHINE.fail_symbol else None)
    return out


def replace(s: str, i: int, c: str) -> str:
    return s[:i] + c + s[i + 1:]


class KnownExamples(unittest.TestCase):
    def test_known_valid_gstins_are_accepted_with_all_checks_passing(self):
        for g in KNOWN_VALID:
            tm = run(g)
            self.assertEqual(tm.status, Status.ACCEPTED, g)
            self.assertTrue(tm.halted_normally)
            self.assertEqual(verdicts(tm), {k: True for k in LABELS}, g)
            self.assertEqual(tm.state, "q_accept")

    def test_oracle_agrees_with_known_valid_examples(self):
        for g in KNOWN_VALID:
            self.assertTrue(oracle_valid(g))

    def test_last_character_is_not_format_restricted(self):
        for c in ALPHABET:
            tm = run(replace(KNOWN_VALID[0], 14, c))
            self.assertEqual(tm.status, Status.ACCEPTED, c)
            self.assertTrue(all(verdicts(tm).values()), c)

    def test_default_character_and_length_failures(self):
        tm = run("27AAPFU0939F1AA")
        self.assertEqual(verdicts(tm)["Default character check"], False)
        self.assertEqual(tm.status, Status.REJECTED)
        tm = run("27AAPFU0939F1Z")
        self.assertEqual(verdicts(tm)["Length check"], False)
        self.assertEqual(tm.status, Status.REJECTED)
        tm = run("369296450896540")
        v = verdicts(tm)
        self.assertEqual((v["Length check"], v["PAN structure check"]), (True, False))
        self.assertEqual(tm.status, Status.REJECTED)


class IndividualChecks(unittest.TestCase):
    BASE = "27AAPFU0939F1ZV"

    def test_incorrect_lengths(self):
        cases = ["", "2", "27", "27AAPFU0939F1Z", "27AAPFU0939F1ZVV", "27AAPFU0939F1ZV" * 2,
                 "A" * 14, "A" * 16, "0" * 30]
        for s in cases:
            tm = run(s)
            v = verdicts(tm)
            self.assertEqual(tm.status, Status.REJECTED, repr(s))
            self.assertIs(v["Length check"], False, repr(s))
            for k in LABELS[1:]:
                self.assertIsNone(v[k], (s, k))                # later checks are not evaluated
        self.assertEqual(run("").steps, 8)

    def test_state_codes_all_two_digit_prefixes(self):
        for a, b in itertools.product("0123456789", repeat=2):
            s = a + b + self.BASE[2:]
            v = verdicts(run(s))
            self.assertEqual(v["State code check"], (a + b) in VALID_STATE_CODES, a + b)
            self.assertTrue(v["PAN structure check"] and v["Entity number check"])

    def test_state_code_with_letters_is_invalid(self):
        for prefix in ("A7", "2A", "AA", "7A", "Z9"):
            self.assertIs(verdicts(run(prefix + self.BASE[2:]))["State code check"], False, prefix)

    def test_pan_structure_each_position_each_symbol(self):
        for i in range(2, 12):
            for c in ALPHABET:
                s = replace(self.BASE, i, c)
                expected = oracle(s)["PAN structure check"]
                self.assertEqual(verdicts(run(s))["PAN structure check"], expected, (i, c))

    def test_malformed_pan_examples(self):
        for s in ("27AAPF10939F1ZV", "27AAPFUA939F1ZV", "27AAPFU09391" + "1ZV", "2711111111111ZV",
                  "27AAPFUAAAAF1ZV", "27AAPFU0939" + "91ZV"):
            self.assertIs(verdicts(run(s))["PAN structure check"], False, s)

    def test_entity_number_every_symbol(self):
        for c in ALPHABET:
            v = verdicts(run(replace(self.BASE, 12, c)))
            self.assertEqual(v["Entity number check"], c != "0", c)

    def test_default_character_every_symbol(self):
        for c in ALPHABET:
            v = verdicts(run(replace(self.BASE, 13, c)))
            self.assertEqual(v["Default character check"], c == "Z", c)

    def test_last_character_every_symbol(self):
        for c in ALPHABET:
            tm = run(replace(self.BASE, 14, c))
            self.assertTrue(all(verdicts(tm).values()), c)
            self.assertEqual(tm.status, Status.ACCEPTED, c)

    def test_each_failure_is_reported_independently(self):
        s = "00" + "AAPFU0939F" + "0" + "Q" + "9"
        v = verdicts(run(s))
        self.assertEqual(v["Length check"], True)
        self.assertEqual(v["State code check"], False)
        self.assertEqual(v["PAN structure check"], True)
        self.assertEqual(v["Entity number check"], False)
        self.assertEqual(v["Default character check"], False)
        self.assertEqual(v, oracle(s))


class InvalidAlphabet(unittest.TestCase):
    def test_symbols_outside_the_gstin_alphabet_are_invalid_input(self):
        for s in ("27aapfu0939f1zv", "27AAPFU0939F1Z-", "27AAPFU0939 F1ZV", " 27AAPFU0939F1ZV",
                  "27AAPFU0939F1ZV\n", "27AAPFU0939F1Z_", "27AAPFU0939F1Z<", "27AAPFU0939F1Z#",
                  "27AAPFU0939F1Z$", "27AAPFU0939F1Z✓", "27AAPFU0939F1Z\u00e9"):
            tm = TuringMachine(GSTIN_MACHINE, s)
            self.assertEqual(tm.status, Status.INVALID_INPUT, repr(s))
            self.assertEqual(tm.run(), Status.INVALID_INPUT)
            self.assertEqual((tm.steps, tm.history), (0, ()))
            self.assertFalse(tm.halted_normally)

    def test_blank_symbol_is_not_the_letter_B(self):
        self.assertNotIn(GSTIN_MACHINE.blank, GSTIN_MACHINE.input_alphabet)
        self.assertEqual(run("27AAPFU0939F1ZV").status, Status.ACCEPTED)
        self.assertIn("B", GSTIN_MACHINE.input_alphabet)
        self.assertEqual(verdicts(run("27BBPFU0939F1ZV"))["PAN structure check"], True)


class OracleComparison(unittest.TestCase):
    def assert_matches_oracle(self, s):
        tm = run(s)
        self.assertEqual(verdicts(tm), oracle(s), s)
        self.assertEqual(tm.status, Status.ACCEPTED if oracle_valid(s) else Status.REJECTED, s)
        self.assertTrue(tm.halted_normally, s)
        return tm

    def test_random_strings_of_length_15(self):
        rng = random.Random(20261104)
        for _ in range(150):
            self.assert_matches_oracle("".join(rng.choice(ALPHABET) for _ in range(15)))

    def test_random_near_valid_strings(self):
        rng = random.Random(7)
        for _ in range(150):
            s = "".join(rng.choice("0123") for _ in range(2))
            s += "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))
            s += "".join(rng.choice("0123456789") for _ in range(4))
            s += rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + rng.choice("123456789ABC") + "Z"
            s += rng.choice(ALPHABET)
            self.assert_matches_oracle(s)

    def test_generated_valid_gstin_formats_are_accepted(self):
        rng = random.Random(99)
        count = 0
        for _ in range(60):
            first14 = (rng.choice(sorted(VALID_STATE_CODES))
                       + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))
                       + "".join(rng.choice("0123456789") for _ in range(4))
                       + rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                       + rng.choice(ALPHABET[1:]) + "Z")
            s = first14 + rng.choice(ALPHABET)
            self.assertEqual(self.assert_matches_oracle(s).status, Status.ACCEPTED, s)
            count += 1
        self.assertEqual(count, 60)

    def test_single_character_mutations_of_valid_gstins(self):
        rng = random.Random(5)
        for base in KNOWN_VALID:
            for i in range(15):
                for c in rng.sample(ALPHABET, 4):
                    self.assert_matches_oracle(replace(base, i, c))

    def test_regex_rejects_invalid_structure(self):
        for s in ("0" * 15, "Z" * 15, "9" * 15, "1" * 14 + "0",
                  "27AAPFU0939F0Z5", "27AAPFU0939F1A5", "27AAPFU0939F1Z"):
            self.assert_matches_oracle(s)

class EngineBehaviour(unittest.TestCase):
    S = "27AAPFU0939F1ZV"

    def test_step_by_step_equals_run(self):
        for s in (self.S, "27AAPFU0939F1Z", ""):
            full = run(s)
            stepper = TuringMachine(GSTIN_MACHINE, s)
            guard = 0
            while not stepper.halted:
                self.assertIsNotNone(stepper.step())
                guard += 1
                self.assertLess(guard, LIMIT)
            self.assertEqual(stepper.status, full.status)
            self.assertEqual(stepper.get_configuration(), full.get_configuration())
            self.assertEqual(stepper.history, full.history)

    def test_reset_restores_initial_configuration(self):
        fresh = TuringMachine(GSTIN_MACHINE, self.S).get_configuration()
        self.assertEqual((fresh.step, fresh.state, fresh.head, fresh.cells),
                         (0, "q0", 0, tuple(enumerate(self.S))))
        tm = TuringMachine(GSTIN_MACHINE, self.S)
        for _ in range(500):
            tm.step()
        self.assertNotEqual(tm.get_configuration(), fresh)
        tm.reset()
        self.assertEqual(tm.get_configuration(), fresh)
        self.assertEqual((tm.history, tm.status), ((), Status.RUNNING))
        tm.run(LIMIT)
        tm.reset()
        self.assertEqual(tm.get_configuration(), fresh)

    def test_tape_movement_uses_negative_positions_and_blank_cells(self):
        tm = run(self.S)
        cfg = tm.get_configuration()
        self.assertEqual(cfg.span[0], -7)                      # verdict cells extend left of the input
        self.assertEqual(cfg.symbol_at(-2), "<")
        self.assertEqual(cfg.symbol_at(-1), "$")
        self.assertEqual([cfg.symbol_at(p) for p in range(-7, -2)], ["✓"] * 5)
        self.assertEqual("".join(cfg.symbol_at(p) for p in range(15)), self.S)
        self.assertEqual(cfg.symbol_at(15), GSTIN_MACHINE.blank)
        self.assertEqual({r.move for r in tm.history}, {"L", "R"})
        # prologue: first transitions move the head left of the input into blank cells
        self.assertEqual([r.head_after for r in tm.history[:4]], [-1, -2, -1, 0])
        self.assertEqual([r.read for r in tm.history[1:3]], ["_", "_"])

    def test_history_replays_on_an_independent_tape(self):
        for s in (self.S, "27AAPFU0939F1ZVX", "Z" * 15):
            tm = run(s)
            cells = dict(enumerate(s))
            head, state = 0, GSTIN_MACHINE.initial_state
            self.assertEqual(len(tm.history), tm.steps)
            for i, r in enumerate(tm.history, 1):
                self.assertEqual((r.step, r.state_before, r.head_before), (i, state, head))
                self.assertEqual(r.read, cells.get(head, GSTIN_MACHINE.blank))
                self.assertEqual(GSTIN_MACHINE.transitions[(r.state_before, r.read)],
                                 (r.state_after, r.write, r.move))
                cells[head] = r.write
                head += 1 if r.move == "R" else -1
                state = r.state_after
                self.assertEqual(r.head_after, head)
            self.assertEqual((state, head), (tm.state, tm.tape.head))
            final = {p: c for p, c in cells.items() if c != GSTIN_MACHINE.blank}
            self.assertEqual(dict(tm.get_configuration().cells), final)

    def test_step_limit_gives_timeout_never_rejection(self):
        tm = TuringMachine(GSTIN_MACHINE, self.S)
        self.assertEqual(tm.run(max_steps=1), Status.TIMEOUT)
        self.assertEqual((tm.steps, tm.halted, tm.halted_normally), (1, False, False))
        self.assertNotIn(tm.status, (Status.ACCEPTED, Status.REJECTED))
        self.assertEqual(tm.run(max_steps=LIMIT), Status.ACCEPTED)       # resumes to the real answer
        self.assertEqual(tm.get_configuration(), run(self.S).get_configuration())
        # an invalid GSTIN under a small limit is also TIMEOUT, not REJECTED
        tm = TuringMachine(GSTIN_MACHINE, "27AAPFU0939F1Z5")
        self.assertEqual(tm.run(max_steps=50), Status.TIMEOUT)

    def test_default_step_limit_is_enough_for_worst_case_inputs(self):
        worst = 0
        for s in ("Z" * 15, "ZZZZZZZZZZZZZZZ", "Y" * 15, "9" * 15 + "", "ZZZZZZZZZZZZZZ0", "IIIIIIIIIIIIIII"):
            tm = run(s)
            worst = max(worst, tm.steps)
            self.assertTrue(tm.halted_normally, s)
        self.assertLess(worst, GSTIN_MACHINE.default_step_limit)

    def test_missing_transitions_are_reported_not_invented(self):
        broken = make_machine({("s0", "0"): ("acc", "0", "R")}, ("s0", "acc", "rej"), "0", "0B")
        tm = TuringMachine(broken, "")
        self.assertEqual(tm.run(), Status.UNDEFINED_TRANSITION)
        self.assertNotIn(tm.status, (Status.ACCEPTED, Status.REJECTED))
        self.assertIs(type(TuringMachine(GSTIN_MACHINE)), type(TuringMachine(LOOPER)))


class DefinitionDiscipline(unittest.TestCase):
    def test_definition_is_total_and_has_only_two_halting_states(self):
        self.assertEqual(GSTIN_MACHINE.missing_transitions(), [])
        self.assertEqual(GSTIN_MACHINE.halting_states, ("q_accept", "q_reject"))

    def test_designed_rules_are_the_only_ones_ever_executed(self):
        """The filler rules that only make δ total must never fire on any input."""
        defensive = GSTIN_MACHINE.defensive_transitions
        self.assertTrue(defensive)
        self.assertEqual(set(GSTIN_MACHINE.transitions) - defensive, set(GSTIN_EXPLICIT_TRANSITIONS))
        rng = random.Random(42)
        inputs = ["", "0", "27AAPFU0939F1ZV", "Z" * 15, "A" * 16, "0" * 14]
        inputs += ["".join(rng.choice(ALPHABET) for _ in range(rng.choice([3, 14, 15, 15, 15, 16])))
                   for _ in range(120)]
        inputs += [replace(KNOWN_VALID[0], i, c) for i in range(15) for c in "0AZ"]
        used = set()
        for s in inputs:
            tm = run(s)
            used |= {(r.state_before, r.read) for r in tm.history}
        self.assertFalse(used & defensive, sorted(used & defensive)[:5])

    def test_result_cells_and_symbols(self):
        self.assertEqual(list(GSTIN_MACHINE.result_cells.values()), [-3, -4, -5, -6, -7])
        self.assertEqual(len(GSTIN_MACHINE.states), 88)
        self.assertEqual((GSTIN_MACHINE.accept_label, GSTIN_MACHINE.reject_label),
                         ("VALID GSTIN", "INVALID GSTIN"))
        self.assertIn("registered", GSTIN_MACHINE.disclaimer)

    def test_state_code_rules_match_the_published_list(self):
        # every valid code accepted, every other 2-digit code rejected, by the machine itself
        accepted = {a + b for a, b in itertools.product("0123456789", repeat=2)
                    if verdicts(run(a + b + "AAPFU0939F1ZV"))["State code check"]}
        self.assertEqual(accepted, VALID_STATE_CODES)
        self.assertEqual(len(accepted), 40)


if __name__ == "__main__":
    unittest.main()
