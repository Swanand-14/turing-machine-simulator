"""Reusable Turing Machine execution engine.

The engine knows nothing about specific languages. It executes whatever
`MachineDefinition` it is given, one explicit transition at a time.

Outcomes (see `Status`)
-----------------------
ACCEPTED              the machine entered an accepting state
REJECTED              the machine entered a rejecting state
INVALID_INPUT         the input contains symbols outside Σ; nothing was executed
TIMEOUT               `run` hit its step limit; the machine has NOT halted and
                      can be resumed. This is never reported as a rejection.
UNDEFINED_TRANSITION  δ had no entry for (state, symbol); a definition error,
                      reported separately and never as ACCEPT or REJECT
RUNNING               not halted yet (initial or paused configuration)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from .machine_definitions import MachineDefinition, Rule
from .tape import Tape

DEFAULT_STEP_LIMIT = 10_000


class Status(str, Enum):
    RUNNING = "RUNNING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID_INPUT = "INVALID INPUT"
    TIMEOUT = "TIMEOUT"
    UNDEFINED_TRANSITION = "UNDEFINED TRANSITION"


_HALTED = frozenset(
    {Status.ACCEPTED, Status.REJECTED, Status.INVALID_INPUT, Status.UNDEFINED_TRANSITION}
)


@dataclass(frozen=True)
class Configuration:
    """Immutable snapshot of a computation (enough to reproduce it)."""

    step: int
    state: str
    head: int
    cells: Tuple[Tuple[int, str], ...]      # non-blank cells, sorted by position
    blank: str
    status: Status
    span: Tuple[int, int]                   # (lowest, highest) position occupied so far

    def symbol_at(self, position: int) -> str:
        return dict(self.cells).get(position, self.blank)

    @property
    def head_symbol(self) -> str:
        return self.symbol_at(self.head)


@dataclass(frozen=True)
class TransitionRecord:
    """One executed transition: (state_before, read) -> (state_after, write, move)."""

    step: int                # 1-based index of this transition
    state_before: str
    read: str
    write: str
    move: str
    state_after: str
    head_before: int
    head_after: int

    def as_text(self) -> str:
        return f"({self.state_before}, {self.read}) → ({self.state_after}, {self.write}, {self.move})"


class TuringMachine:
    """Deterministic single-tape Turing Machine simulator."""

    def __init__(self, definition: MachineDefinition, input_string: str = "") -> None:
        self.definition = definition
        self._input = ""
        self.initialize(input_string)

    # ------------------------------------------------------------- lifecycle
    def initialize(self, input_string: str) -> None:
        """Validate the input and load the initial configuration.

        If any character is outside Σ the status becomes INVALID_INPUT and no
        transition is ever executed. The empty string is valid input.
        """
        d = self.definition
        self._input = input_string
        self.invalid_symbols: Tuple[str, ...] = tuple(
            sorted({c for c in input_string if c not in d.input_alphabet})
        )
        self.tape = Tape(d.blank)
        self.state = d.initial_state
        self.steps = 0
        self._history: List[TransitionRecord] = []
        self.error: Optional[str] = None
        if self.invalid_symbols:
            self.status = Status.INVALID_INPUT
            return
        self.tape.load(input_string)
        self.status = Status.RUNNING
        self._refresh_status()

    def reset(self) -> None:
        """Restore the initial configuration for the current input."""
        self.initialize(self._input)

    # ------------------------------------------------------------ execution
    def step(self) -> Optional[TransitionRecord]:
        """Execute exactly one transition.

        Returns the executed `TransitionRecord`, or None when nothing was
        executed (machine already halted, or no rule exists for the current
        (state, symbol), in which case status becomes UNDEFINED_TRANSITION).
        """
        if self.status == Status.TIMEOUT:      # resuming after a step limit
            self.status = Status.RUNNING
        if self.halted:
            return None

        read = self.tape.read()
        rule = self.definition.transitions.get((self.state, read))
        if rule is None:
            self.status = Status.UNDEFINED_TRANSITION
            self.error = f"No transition defined for ({self.state}, {read})."
            return None

        next_state, write, move = rule
        head_before = self.tape.head
        self.tape.write(write)
        self.tape.move(move)
        self.steps += 1
        record = TransitionRecord(
            step=self.steps,
            state_before=self.state,
            read=read,
            write=write,
            move=move,
            state_after=next_state,
            head_before=head_before,
            head_after=self.tape.head,
        )
        self._history.append(record)
        self.state = next_state
        self._refresh_status()
        return record

    def run(self, max_steps: int = DEFAULT_STEP_LIMIT) -> Status:
        """Run until the machine halts or `max_steps` more transitions were executed.

        If the limit is reached first, status is TIMEOUT (not REJECTED) and the
        machine can be resumed with `step()` or `run()`.
        """
        if max_steps < 0:
            raise ValueError("max_steps must be non-negative.")
        if self.status == Status.TIMEOUT:
            self.status = Status.RUNNING
        executed = 0
        while not self.halted:
            if executed >= max_steps:
                self.status = Status.TIMEOUT
                break
            self.step()
            executed += 1
        return self.status

    def _refresh_status(self) -> None:
        d = self.definition
        if self.state in d.accept_states:
            self.status = Status.ACCEPTED
        elif self.state in d.reject_states:
            self.status = Status.REJECTED
        else:
            self.status = Status.RUNNING

    # ----------------------------------------------------------- inspection
    @property
    def input_string(self) -> str:
        return self._input

    @property
    def halted(self) -> bool:
        return self.status in _HALTED

    @property
    def halted_normally(self) -> bool:
        """True only when the machine stopped in an accepting or rejecting state."""
        return self.status in (Status.ACCEPTED, Status.REJECTED)

    @property
    def history(self) -> Tuple[TransitionRecord, ...]:
        return tuple(self._history)

    def next_transition(self) -> Optional[Tuple[str, str, Optional[Rule]]]:
        """(state, symbol under head, rule or None) for the next step, or None if halted."""
        if self.halted:
            return None
        read = self.tape.read()
        return self.state, read, self.definition.transitions.get((self.state, read))

    def get_configuration(self) -> Configuration:
        return Configuration(
            step=self.steps,
            state=self.state,
            head=self.tape.head,
            cells=self.tape.snapshot(),
            blank=self.definition.blank,
            status=self.status,
            span=self.tape.bounds(),
        )
