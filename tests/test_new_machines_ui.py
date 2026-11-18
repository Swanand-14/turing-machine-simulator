"""Presentation-layer tests for the palindrome and GSTIN machines."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tm import GSTIN_MACHINE, L1_MACHINE, L2_MACHINE, MACHINES, PAL_MACHINE, Status, TuringMachine
from tm.visualization import (
    compress_symbols,
    grouped_transition_rows,
    tape_window,
    to_dot,
    to_phase_overview_dot,
)


def expand_symbols(text, definition):
    """Inverse of compress_symbols (used only to check the grouped table)."""
    out = set()
    for token in text.split(", "):
        if token == "Σ":
            out |= set(definition.input_alphabet)
        elif len(token) == 3 and token[1] == "–":
            out |= {chr(c) for c in range(ord(token[0]), ord(token[2]) + 1)}
        else:
            out.add(token)
    return out


def expand_grouped(definition):
    """Rebuild {(state, read): (next, write, move)} from the grouped table."""
    order = list(definition.input_alphabet)
    rebuilt = {}
    for row in grouped_transition_rows(definition):
        for read in expand_symbols(row["Read Symbol"], definition):
            w = row["Write Symbol"]
            if w == "same":
                w = read
            elif w == "pred(read)":
                w = order[order.index(read) - 1]
            elif w.startswith("succ(read)"):
                w = order[(order.index(read) + 1) % len(order)]
            key = (row["Current State"], read)
            assert key not in rebuilt, f"{key} listed twice"
            rebuilt[key] = (row["Next State"], w, row["Direction"])
    return rebuilt


class RegistryTests(unittest.TestCase):
    def test_four_machines_in_the_expected_order(self):
        self.assertEqual(list(MACHINES), ["L1", "L2", "PAL", "GSTIN"])
        self.assertIs(MACHINES["L1"], L1_MACHINE)
        self.assertIs(MACHINES["L2"], L2_MACHINE)

    def test_existing_machines_are_unchanged(self):
        self.assertEqual((L1_MACHINE.accept_label, L1_MACHINE.reject_label), ("ACCEPTED", "REJECTED"))
        self.assertEqual(L1_MACHINE.defensive_transitions, frozenset())
        self.assertEqual(L2_MACHINE.defensive_transitions, frozenset())
        self.assertEqual(len(L1_MACHINE.sorted_transitions()), 4 * 5)
        self.assertEqual(len(L2_MACHINE.sorted_transitions()), 6 * 7)


class GroupedTableTests(unittest.TestCase):
    def test_grouped_table_expands_exactly_to_the_real_transitions(self):
        for d in MACHINES.values():
            self.assertEqual(expand_grouped(d), dict(d.transitions), d.key)

    def test_grouped_table_is_much_smaller_for_gstin(self):
        self.assertLess(len(grouped_transition_rows(GSTIN_MACHINE)), 400)
        self.assertGreater(len(GSTIN_MACHINE.transitions), 3500)

    def test_compress_symbols(self):
        d = GSTIN_MACHINE
        self.assertEqual(compress_symbols(list(d.input_alphabet), d), "Σ")
        self.assertEqual(compress_symbols(list("0123456789"), d), "0–9")
        self.assertEqual(compress_symbols(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), d), "A–Z")
        self.assertEqual(compress_symbols(["Z", "A", "<"], d), "A, Z, <")
        self.assertEqual(compress_symbols(list("123456789") + ["A", "B", "C"], d), "1–9, A–C")


class DiagramTests(unittest.TestCase):
    def test_palindrome_diagram_has_all_states_and_labels(self):
        dot = to_dot(PAL_MACHINE, current_state="q1", collapse_rejects=False)
        for st in PAL_MACHINE.states:
            self.assertIn(f'"{st}"', dot)
        for r in PAL_MACHINE.sorted_transitions():
            self.assertIn(f"{r.read}/{r.write},{r.move}", dot)
        self.assertIn('"q1" [shape=circle, color="#e65100", penwidth=4]', dot)

    def test_every_gstin_phase_view_contains_exactly_its_states(self):
        for phase in GSTIN_MACHINE.phase_order:
            dot = to_dot(GSTIN_MACHINE, compact_labels=True, phase=phase)
            mine = [s for s, ph in GSTIN_MACHINE.phases.items() if ph == phase]
            for st in mine:
                self.assertRegex(dot, rf'(?m)^  "{re.escape(st)}" \[', msg=(phase, st))
        # the PAN pass never routes to q_reject by design: no filler edges are drawn for it
        self.assertNotIn("q_reject", to_dot(GSTIN_MACHINE, compact_labels=True, phase="3. PAN structure"))

    def test_phase_view_edges_come_from_real_non_filler_rules(self):
        d = GSTIN_MACHINE
        real_pairs = {(r.state, r.next_state) for r in d.sorted_transitions()
                      if (r.state, r.read) not in d.defensive_transitions}
        dot = to_dot(d, compact_labels=True)
        drawn = set(re.findall(r'^  "([^"]+)" -> "([^"]+)" \[label', dot, flags=re.M))
        self.assertEqual(drawn, real_pairs)
        self.assertNotEqual(drawn, {(r.state, r.next_state) for r in d.sorted_transitions()})

    def test_overview_edge_counts_match_cross_phase_rules(self):
        d = GSTIN_MACHINE
        dot = to_phase_overview_dot(d, current_state="def14")
        total = sum(int(n) for n in re.findall(r'label="(\d+) rules?"', dot))
        cross = sum(1 for r in d.sorted_transitions()
                    if (r.state, r.read) not in d.defensive_transitions
                    and d.phases[r.state] != d.phases[r.next_state])
        self.assertEqual(total, cross)

    def test_old_diagram_output_for_l1_l2_is_unchanged_by_new_options(self):
        for d in (L1_MACHINE, L2_MACHINE):
            self.assertEqual(to_dot(d, "q0"), to_dot(d, "q0", compact_labels=False, phase=None, show_defensive=False))


class TapeWindowTests(unittest.TestCase):
    def test_gstin_tape_fits_in_the_wide_window_and_shows_negative_cells(self):
        tm = TuringMachine(GSTIN_MACHINE, "27AAPFU0939F1ZV")
        tm.run(100_000)
        cfg = tm.get_configuration()
        w = tape_window(cfg, max_cells=31)
        self.assertEqual((w.hidden_left, w.hidden_right), (0, 0))
        positions = [c.position for c in w.cells]
        self.assertEqual((min(positions), max(positions)), (-9, 17))
        for c in w.cells:
            self.assertEqual(c.symbol, cfg.symbol_at(c.position))
        self.assertEqual(sum(c.is_head for c in w.cells), 1)


try:
    from streamlit.testing.v1 import AppTest
except Exception:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit is not installed")
class AppTests(unittest.TestCase):
    APP = os.path.join(ROOT, "app.py")

    def fresh(self, key=None):
        at = AppTest.from_file(self.APP, default_timeout=120)
        at.run()
        if key:
            at.selectbox[0].select(key).run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def click(at, label):
        next(b for b in at.button if b.label == label).click().run()

    @staticmethod
    def checks_table(at):
        for df in at.dataframe:
            if "Check" in df.value.columns:
                return dict(zip(df.value["Check"], df.value["Result"]))
        return None

    def test_dropdown_lists_the_four_machines(self):
        at = self.fresh()
        self.assertEqual(len(at.selectbox[0].options), 4)
        self.assertIn("Palindrome", at.selectbox[0].options[2])
        self.assertIn("GSTIN", at.selectbox[0].options[3])
        self.assertIsNone(self.checks_table(at))            # only GSTIN shows the checks table

    def test_palindrome_run_accept_reject_and_empty(self):
        at = self.fresh("PAL")
        self.assertEqual(at.text_input[0].value, "1001")
        self.click(at, "Run")
        self.assertTrue(any("ACCEPTED" in s.value for s in at.success))
        at.text_input[0].set_value("10").run()
        self.click(at, "Run")
        self.assertTrue(any("REJECTED" in e.value for e in at.error))
        at.text_input[0].set_value("").run()
        self.click(at, "Run")
        self.assertTrue(any("ACCEPTED" in s.value for s in at.success))
        self.assertEqual(at.session_state["engine"].steps, 1)
        self.assertFalse(at.exception)

    def test_gstin_valid_shows_all_checks_passing(self):
        at = self.fresh("GSTIN")
        self.assertEqual(at.text_input[0].value, "27AAPFU0939F1ZV")
        self.assertEqual(at.number_input[0].value, 10_000)
        self.click(at, "Run")
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(any("VALID GSTIN" in s.value and "INVALID" not in s.value for s in at.success))
        checks = self.checks_table(at)
        self.assertEqual(len(checks), 5)
        self.assertTrue(all("PASS" in v for v in checks.values()), checks)
        self.assertTrue(any("registered" in c.value for c in at.caption))   # disclaimer is shown

    def test_gstin_last_character_can_be_any_alphanumeric(self):
        at = self.fresh("GSTIN")
        at.text_input[0].set_value("27AAPFU0939F1Z5").run()
        self.click(at, "Run")
        self.assertTrue(any("VALID GSTIN" in s.value for s in at.success))
        checks = self.checks_table(at)
        self.assertTrue(all("PASS" in v for v in checks.values()), checks)

    def test_gstin_wrong_length_marks_other_checks_not_evaluated(self):
        at = self.fresh("GSTIN")
        at.text_input[0].set_value("27AAPFU0939F1Z").run()
        self.click(at, "Run")
        checks = self.checks_table(at)
        self.assertIn("FAIL", checks["Length check"])
        self.assertTrue(all(v == "Not evaluated" for k, v in checks.items() if k != "Length check"))

    def test_gstin_lowercase_is_invalid_input(self):
        at = self.fresh("GSTIN")
        at.text_input[0].set_value("27aapfu0939f1zv").run()
        self.assertTrue(any("INVALID INPUT" in w.value for w in at.warning))
        self.assertTrue(any("INVALID GSTIN" in w.value for w in at.warning))
        self.assertTrue(all("Not evaluated" in v for v in self.checks_table(at).values()))

    def test_gstin_stepping_shows_pending_then_progress(self):
        at = self.fresh("GSTIN")
        self.click(at, "Step")
        self.assertEqual(at.session_state["engine"].steps, 1)
        self.assertTrue(all(v == "Pending" for v in self.checks_table(at).values()))
        at.number_input[0].set_value(30).run()
        self.click(at, "Run")
        self.assertTrue(any("TIMEOUT" in w.value for w in at.warning))
        self.assertEqual(len(at.error), 0)
        self.assertEqual(at.session_state["engine"].steps, 31)         # 1 step + 30 more

    def test_gstin_step_then_reset_and_machine_switch_clear_state(self):
        at = self.fresh("GSTIN")
        for _ in range(5):
            self.click(at, "Step")
        self.assertEqual(at.session_state["engine"].steps, 5)
        self.click(at, "Reset")
        self.assertEqual(at.session_state["engine"].steps, 0)
        self.click(at, "Step")
        at.selectbox[0].select("PAL").run()
        eng = at.session_state["engine"]
        self.assertEqual((eng.definition.key, eng.steps, eng.input_string), ("PAL", 0, "1001"))

    def test_every_gstin_diagram_view_and_the_table_toggle_render(self):
        at = self.fresh("GSTIN")
        views = at.selectbox[1].options
        self.assertEqual(views[0], "Overview")
        self.assertEqual(len(views), 9)
        for v in views:
            at.selectbox[1].select(v).run()
            self.assertFalse(at.exception, (v, [e.value for e in at.exception]))
        at.checkbox[0].uncheck().run()                                 # full transition table
        self.assertFalse(at.exception)
        self.assertTrue(any(len(df.value) == len(GSTIN_MACHINE.transitions) for df in at.dataframe))

    def test_small_machines_keep_their_original_full_table(self):
        at = self.fresh("L1")
        self.assertTrue(any(len(df.value) == len(L1_MACHINE.transitions) for df in at.dataframe))


if __name__ == "__main__":
    unittest.main()
