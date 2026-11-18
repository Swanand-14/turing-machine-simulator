"""Tests for the presentation layer: tape window, diagram, and the Streamlit app."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tm import L1_MACHINE, L2_MACHINE, Status, TuringMachine
from tm.visualization import tape_html, tape_window, to_dot


class TapeWindowTests(unittest.TestCase):
    def test_head_cell_matches_configuration_at_every_step(self):
        for d, s in ((L1_MACHINE, "0011"), (L2_MACHINE, "001122")):
            tm = TuringMachine(d, s)
            while True:
                cfg = tm.get_configuration()
                heads = [c for c in tape_window(cfg).cells if c.is_head]
                self.assertEqual(len(heads), 1)
                self.assertEqual(heads[0].position, cfg.head)
                self.assertEqual(heads[0].symbol, cfg.head_symbol)
                for c in tape_window(cfg).cells:
                    self.assertEqual(c.symbol, cfg.symbol_at(c.position))
                if tm.halted:
                    break
                tm.step()

    def test_window_includes_blanks_around_input(self):
        cfg = TuringMachine(L1_MACHINE, "01").get_configuration()
        positions = [c.position for c in tape_window(cfg).cells]
        self.assertEqual(positions, list(range(-2, 4)))

    def test_long_tape_is_clipped_around_head(self):
        cfg = TuringMachine(L1_MACHINE, "0" * 40 + "1" * 40).get_configuration()
        w = tape_window(cfg, max_cells=25)
        self.assertLessEqual(len(w.cells), 25)
        self.assertGreater(w.hidden_right, 0)
        self.assertTrue(any(c.is_head for c in w.cells))

    def test_html_contains_head_marker_and_escapes_symbols(self):
        cfg = TuringMachine(L1_MACHINE, "01").get_configuration()
        out = tape_html(tape_window(cfg), L1_MACHINE)
        self.assertEqual(out.count("HEAD"), 1)
        self.assertNotIn("\n", out)


class DiagramTests(unittest.TestCase):
    def test_uncollapsed_diagram_has_every_transition_label(self):
        for d in (L1_MACHINE, L2_MACHINE):
            dot = to_dot(d, collapse_rejects=False)
            for r in d.sorted_transitions():
                self.assertIn(f"{r.read}/{r.write},{r.move}", dot)
            for s in d.states:
                self.assertIn(f'"{s}"', dot)

    def test_edges_between_same_states_are_merged(self):
        dot = to_dot(L1_MACHINE, collapse_rejects=False)
        self.assertEqual(dot.count('"q0" -> "q1"'), 1)
        self.assertEqual(dot.count('"q1" -> "q1"'), 1)      # 0/0,R and Y/Y,R share one self-loop

    def test_collapsed_diagram_lists_every_reject_symbol(self):
        for d in (L1_MACHINE, L2_MACHINE):
            dot = to_dot(d, collapse_rejects=True)
            self.assertIn("q_reject", dot)
            for r in d.sorted_transitions():
                if r.next_state == "q_reject":
                    line = next(l for l in dot.splitlines() if l.startswith(f'  "{r.state}" -> "q_reject"'))
                    self.assertIn(r.read, line)

    def test_initial_accepting_rejecting_and_current_are_marked(self):
        dot = to_dot(L2_MACHINE, current_state="q3")
        self.assertIn('__start -> "q0"', dot)
        self.assertIn('"q_accept" [shape=doublecircle', dot)
        self.assertIn('"q_reject" [shape=box', dot)
        self.assertIn('"q3" [shape=circle, color="#e65100", penwidth=4]', dot)


try:
    from streamlit.testing.v1 import AppTest
except Exception:  # Streamlit not installed
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit is not installed")
class AppSmokeTests(unittest.TestCase):
    APP = os.path.join(ROOT, "app.py")

    def fresh(self):
        at = AppTest.from_file(self.APP, default_timeout=60)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def click(at, label):
        next(b for b in at.button if b.label == label).click().run()

    def test_initial_page_renders_without_error(self):
        at = self.fresh()
        self.assertEqual(at.title[0].value, "Interactive Turing Machine Simulator")
        self.assertTrue(any("READY" in i.value for i in at.info))

    def test_run_accepts_and_reset_clears(self):
        at = self.fresh()
        self.click(at, "Run")
        self.assertFalse(at.exception)
        self.assertTrue(any("ACCEPTED" in s.value for s in at.success))
        self.click(at, "Reset")
        self.assertFalse(at.exception)
        self.assertEqual(len(at.success), 0)
        self.assertEqual(at.session_state["engine"].steps, 0)

    def test_step_executes_exactly_one_transition_per_click(self):
        at = self.fresh()
        for n in (1, 2, 3):
            self.click(at, "Step")
            self.assertEqual(at.session_state["engine"].steps, n)
            self.assertEqual(len(at.session_state["engine"].history), n)

    def test_changing_input_or_machine_discards_old_state(self):
        at = self.fresh()
        self.click(at, "Step")
        self.click(at, "Step")
        at.text_input[0].set_value("01").run()
        self.assertEqual(at.session_state["engine"].steps, 0)
        self.assertEqual(at.session_state["engine"].input_string, "01")
        self.click(at, "Step")
        at.selectbox[0].select("L2").run()
        eng = at.session_state["engine"]
        self.assertEqual((eng.definition.key, eng.steps), ("L2", 0))

    def test_l2_run_and_rejection_and_invalid_and_timeout(self):
        at = self.fresh()
        at.selectbox[0].select("L2").run()
        at.text_input[0].set_value("000111222").run()
        self.click(at, "Run")
        self.assertTrue(any("ACCEPTED" in s.value for s in at.success))
        at.text_input[0].set_value("00112").run()
        self.click(at, "Run")
        self.assertTrue(any("REJECTED" in e.value for e in at.error))
        at.text_input[0].set_value("0123").run()
        self.assertTrue(any("INVALID INPUT" in w.value for w in at.warning))
        at.text_input[0].set_value("000111222").run()
        at.number_input[0].set_value(5).run()
        self.click(at, "Run")
        self.assertTrue(any("TIMEOUT" in w.value for w in at.warning))
        self.assertEqual(len(at.error), 0)
        self.assertFalse(at.exception)

    def test_rerun_does_not_duplicate_history(self):
        at = self.fresh()
        self.click(at, "Run")
        steps = at.session_state["engine"].steps
        at.checkbox[0].uncheck().run()          # unrelated widget triggers a rerun
        self.assertEqual(at.session_state["engine"].steps, steps)
        self.assertEqual(len(at.session_state["engine"].history), steps)


if __name__ == "__main__":
    unittest.main()
