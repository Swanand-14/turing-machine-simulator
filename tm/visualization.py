"""Presentation helpers (no Streamlit imports, so they can be unit-tested).

* `tape_window` / `tape_html`: choose and render the visible part of the tape.
* `to_dot`: build a Graphviz DOT diagram directly from `definition.transitions`.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .engine import Configuration
from .machine_definitions import MachineDefinition, TransitionRow


# ------------------------------------------------------------------- tape
@dataclass(frozen=True)
class TapeCell:
    position: int
    symbol: str
    is_head: bool


@dataclass(frozen=True)
class TapeWindow:
    cells: Tuple[TapeCell, ...]
    hidden_left: int      # occupied cells off-screen to the left
    hidden_right: int     # occupied cells off-screen to the right


def tape_window(config: Configuration, max_cells: int = 25, padding: int = 2) -> TapeWindow:
    """Choose the cells to display.

    Shows every cell the input/head has occupied plus `padding` blank cells on
    each side. Long tapes are clipped to at most `max_cells` cells centred on
    the head, and the number of hidden cells is reported.
    """
    span_lo, span_hi = config.span
    span_lo = min(span_lo, config.head)
    span_hi = max(span_hi, config.head)
    lo, hi = span_lo - padding, span_hi + padding
    if hi - lo + 1 > max_cells:
        radius = max_cells // 2
        lo, hi = max(lo, config.head - radius), min(hi, config.head + radius)
    cells = tuple(
        TapeCell(p, config.symbol_at(p), p == config.head) for p in range(lo, hi + 1)
    )
    return TapeWindow(cells, max(0, lo - span_lo), max(0, span_hi - hi))


def tape_html(window: TapeWindow, definition: MachineDefinition) -> str:
    """HTML for the tape row: cells, position indices, and a HEAD marker.

    Built on one line (no indentation) so Streamlit's markdown does not treat
    it as a code block.
    """
    sigma = set(definition.input_alphabet)
    border = "2px solid rgba(128,128,128,0.85)"

    def cell_style(c: TapeCell) -> str:
        base = (
            f"width:44px;height:44px;box-sizing:border-box;border:{border};"
            "display:flex;align-items:center;justify-content:center;"
            "font:700 20px monospace;margin-right:-2px;"
        )
        if c.is_head:
            return base + "background:#ffd54f;color:#000;border-color:#e65100;position:relative;z-index:1;"
        if c.symbol == definition.blank:
            return base + "opacity:0.55;"
        if c.symbol in sigma:
            return base
        return base + "background:rgba(66,133,244,0.28);"          # marker symbols X, Y, Z

    def gap(text: str) -> str:
        return (
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:flex-start;min-width:44px;">'
            f'<div style="height:44px;display:flex;align-items:center;font:700 16px monospace;opacity:0.7;">'
            f"{html.escape(text)}</div></div>"
        )

    parts: List[str] = ['<div style="display:flex;align-items:flex-start;overflow-x:auto;padding:6px 2px 10px 2px;">']
    if window.hidden_left:
        parts.append(gap(f"…{window.hidden_left}"))
    for c in window.cells:
        marker = (
            '<div style="font:700 11px monospace;color:#e65100;line-height:1.15;text-align:center;">▲<br>HEAD</div>'
            if c.is_head else '<div style="height:26px;"></div>'
        )
        parts.append(
            '<div style="display:flex;flex-direction:column;align-items:center;">'
            f'<div style="{cell_style(c)}">{html.escape(c.symbol)}</div>'
            f'<div style="font:11px monospace;opacity:0.65;margin-top:3px;">{c.position}</div>'
            f"{marker}</div>"
        )
    if window.hidden_right:
        parts.append(gap(f"{window.hidden_right}…"))
    parts.append("</div>")
    return "".join(parts)


# ------------------------------------------------- compact descriptions
def _consecutive(a: str, b: str) -> bool:
    """True if b directly follows a within the digits or within A-Z."""
    return ord(b) == ord(a) + 1 and (
        (a.isdigit() and b.isdigit()) or ("A" <= a <= "Z" and "A" <= b <= "Z")
    )


def compress_symbols(symbols: Sequence[str], definition: MachineDefinition) -> str:
    """Readable set notation: 'Σ', '0–9', 'A–Z', or a comma list, in tape-alphabet order."""
    wanted = set(symbols)
    ordered = [s for s in definition.tape_alphabet if s in wanted]
    sigma = set(definition.input_alphabet)
    parts: List[str] = []
    if len(sigma) > 4 and sigma <= wanted:
        parts.append("Σ")
        ordered = [s for s in ordered if s not in sigma]
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and _consecutive(ordered[j], ordered[j + 1]):
            j += 1
        if j - i >= 2:
            parts.append(f"{ordered[i]}–{ordered[j]}")
        else:
            parts.extend(ordered[i:j + 1])
        i = j + 1
    return ", ".join(parts)


def describe_rules(
    definition: MachineDefinition, rows: Sequence[TransitionRow]
) -> List[Tuple[str, str, str]]:
    """Summarise rules that share the same (state, next state).

    Returns (read symbols, write description, move) triples. Rules are merged
    only when they really are uniform: 'same' (write = read), 'pred(read)' /
    'succ(read)' (the written symbol is the neighbour of the read symbol in
    the input alphabet), or one constant written symbol.
    """
    order = list(definition.input_alphabet)
    index = {s: i for i, s in enumerate(order)}
    out: List[Tuple[str, str, str]] = []
    by_move: Dict[str, List[TransitionRow]] = {}
    for r in rows:
        by_move.setdefault(r.move, []).append(r)
    for move, rs in by_move.items():
        same = [r.read for r in rs if r.write == r.read]
        other = [r for r in rs if r.write != r.read]
        if same:
            out.append((compress_symbols(same, definition), "same", move))
        if not other:
            continue
        if len(other) >= 4 and all(r.read in index and r.write in index for r in other):
            reads = [r.read for r in other]
            if all(index[r.write] == index[r.read] - 1 for r in other):
                out.append((compress_symbols(reads, definition), "pred(read)", move))
                continue
            if all(index[r.write] == (index[r.read] + 1) % len(order) for r in other):
                out.append((compress_symbols(reads, definition),
                            f"succ(read) mod {len(order)}", move))
                continue
        by_write: Dict[str, List[str]] = {}
        for r in other:
            by_write.setdefault(r.write, []).append(r.read)
        for w, reads in by_write.items():
            out.append((compress_symbols(reads, definition), w, move))
    return out


def _is_defensive(definition: MachineDefinition, row: TransitionRow) -> bool:
    return (row.state, row.read) in definition.defensive_transitions


def grouped_transition_rows(definition: MachineDefinition) -> List[Dict[str, str]]:
    """Grouped (compact) view of the full transition table.

    Same data as `definition.sorted_transitions()`, merged per (state, next
    state, defensive flag). The un-grouped table is always available.
    """
    groups: Dict[Tuple[str, str, bool], List[TransitionRow]] = {}
    for row in definition.sorted_transitions():
        groups.setdefault((row.state, row.next_state, _is_defensive(definition, row)), []).append(row)
    out: List[Dict[str, str]] = []
    for (state, nxt, defensive), rows in groups.items():
        for reads, write, move in describe_rules(definition, rows):
            entry = {
                "Current State": state,
                "Read Symbol": reads,
                "Write Symbol": write,
                "Direction": move,
                "Next State": nxt,
            }
            if definition.defensive_transitions:
                entry["Note"] = "totality filler (never executed)" if defensive else ""
            out.append(entry)
    return out


# ---------------------------------------------------------------- diagram
def _q(text: str) -> str:
    return '"' + text.replace('"', '\\"') + '"'


def _join(labels: List[str]) -> str:
    """Join edge labels with DOT's newline escape (backslash + n)."""
    return "\\n".join(labels)


_HEADER = [
    "digraph TM {",
    '  rankdir=LR; bgcolor="white"; pad=0.2;',
    '  node [fontname="Helvetica", fontsize=13, style=filled, fillcolor="white", color="#333333", fontcolor="black"];',
    '  edge [fontname="Helvetica", fontsize=11, color="#333333", fontcolor="black"];',
]


def _node_attrs(definition: MachineDefinition, state: str, current_state: Optional[str]) -> str:
    if state in definition.accept_states:
        attrs = 'shape=doublecircle, fillcolor="#c8e6c9"'
    elif state in definition.reject_states:
        attrs = 'shape=box, fillcolor="#ffcdd2"'
    else:
        attrs = "shape=circle"
    if state == current_state:
        attrs += ', color="#e65100", penwidth=4'
    return attrs


def to_dot(
    definition: MachineDefinition,
    current_state: Optional[str] = None,
    collapse_rejects: bool = True,
    compact_labels: bool = False,
    phase: Optional[str] = None,
    show_defensive: bool = False,
) -> str:
    """Graphviz DOT for the machine, derived only from `definition.transitions`.

    Edge label format:  read/write,move.
    Transitions between the same pair of states share one edge (one label per
    line). With `collapse_rejects`, the many "wrong symbol -> q_reject"
    transitions that leave a state unchanged are drawn as one dashed edge
    listing the symbols read; nothing is added or removed, only grouped.

    `compact_labels` merges uniform rules per edge using set notation
    ('Σ / same,R', '1–9, A–Z / pred(read),L'). `phase` draws only the states
    of one phase (neighbouring states outside it appear as dashed boxes).
    Totality-filler rules (`definition.defensive_transitions`) are hidden
    unless `show_defensive` is set.
    """
    rejects = set(definition.reject_states)
    all_rows = [
        r for r in definition.sorted_transitions()
        if show_defensive or not _is_defensive(definition, r)
    ]
    if phase is not None:
        in_phase = {s for s, ph in definition.phases.items() if ph == phase}
        rows = [r for r in all_rows if r.state in in_phase or r.next_state in in_phase]
        visible = [s for s in definition.states if s in in_phase]
        externals = sorted(
            ({r.state for r in rows} | {r.next_state for r in rows}) - in_phase,
            key=definition.states.index,
        )
    else:
        in_phase = set(definition.states)
        rows = all_rows
        visible = list(definition.states)
        externals = []

    edges: Dict[Tuple[str, str, bool], List[str]] = {}
    if compact_labels:
        groups: Dict[Tuple[str, str], List[TransitionRow]] = {}
        for r in rows:
            groups.setdefault((r.state, r.next_state), []).append(r)
        for (src, dst), rs in groups.items():
            edges[(src, dst, dst in rejects)] = [
                f"{reads} / {write},{move}" for reads, write, move in describe_rules(definition, rs)
            ]
    else:
        grouped_rejects: Dict[Tuple[str, str, str], List[str]] = {}
        for row in rows:
            to_reject = row.next_state in rejects
            if collapse_rejects and to_reject and row.write == row.read:
                grouped_rejects.setdefault((row.state, row.next_state, row.move), []).append(row.read)
            else:
                edges.setdefault((row.state, row.next_state, to_reject), []).append(
                    f"{row.read}/{row.write},{row.move}"
                )
        for (src, dst, move), reads in grouped_rejects.items():
            edges.setdefault((src, dst, True), []).append(f"{', '.join(reads)} / same,{move}")

    lines = list(_HEADER)
    if definition.initial_state in visible:
        lines.append('  __start [shape=point, width=0.15, label="", fillcolor="#333333"];')
        lines.append(f"  __start -> {_q(definition.initial_state)} [label=\"start\"];")
    for st in visible:
        lines.append(f"  {_q(st)} [{_node_attrs(definition, st, current_state)}];")
    for st in externals:
        attrs = _node_attrs(definition, st, current_state)
        if st in definition.accept_states or st in rejects:
            lines.append(f"  {_q(st)} [{attrs}];")
        else:
            lines.append(f"  {_q(st)} [shape=box, style=\"dashed,filled\", fillcolor=\"#eeeeee\", "
                         f"label={_q(st + chr(92) + 'n(' + definition.phases.get(st, '') + ')')}];")
    for (src, dst, to_reject), labels in edges.items():
        style = ', style=dashed, color="#b71c1c", fontcolor="#b71c1c"' if to_reject else ""
        lines.append(f"  {_q(src)} -> {_q(dst)} [label={_q(_join(labels))}{style}];")
    lines.append("}")
    return "\n".join(lines)


def to_phase_overview_dot(definition: MachineDefinition, current_state: Optional[str] = None) -> str:
    """One node per phase; an edge A -> B per pair of phases linked by real transitions.

    Derived from `definition.phases` and `definition.transitions`; edge labels
    give the number of (non-filler) transitions that cross between the phases.
    """
    order = list(definition.phase_order) or sorted(set(definition.phases.values()))
    counts: Dict[Tuple[str, str], int] = {}
    sizes: Dict[str, int] = {}
    for st in definition.states:
        sizes[definition.phases.get(st, "")] = sizes.get(definition.phases.get(st, ""), 0) + 1
    for r in definition.sorted_transitions():
        if _is_defensive(definition, r):
            continue
        a, b = definition.phases.get(r.state, ""), definition.phases.get(r.next_state, "")
        if a != b:
            counts[(a, b)] = counts.get((a, b), 0) + 1
    current_phase = definition.phases.get(current_state or "", None)
    lines = list(_HEADER)
    first_phase = definition.phases.get(definition.initial_state, "")
    lines.append('  __start [shape=point, width=0.15, label="", fillcolor="#333333"];')
    lines.append(f"  __start -> {_q(first_phase)};")
    for ph in order:
        attrs = f'shape=box, style="rounded,filled", label={_q(ph + chr(92) + "n" + str(sizes.get(ph, 0)) + " states")}'
        if ph == current_phase:
            attrs += ', color="#e65100", penwidth=4'
        lines.append(f"  {_q(ph)} [{attrs}];")
    for (a, b), n in counts.items():
        lines.append(f"  {_q(a)} -> {_q(b)} [label={_q(str(n) + ' rule' + ('s' if n != 1 else ''))}];")
    lines.append("}")
    return "\n".join(lines)
