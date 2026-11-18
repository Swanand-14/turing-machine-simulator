"""Two-way infinite tape with an independently tracked read/write head.

Cells are stored in a dictionary indexed by integer positions, so the head can
move to any position (including negative ones) without index errors.
Any position that has never been written reads as the blank symbol.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

LEFT = "L"
RIGHT = "R"
DIRECTIONS = (LEFT, RIGHT)


class Tape:
    """A tape that is infinite in both directions.

    Only non-blank cells are stored. Writing the blank symbol erases a cell,
    which keeps tape snapshots canonical (two tapes with the same visible
    contents have equal snapshots).
    """

    def __init__(self, blank: str = "B", contents: Iterable[str] = ()) -> None:
        if len(blank) != 1:
            raise ValueError("The blank symbol must be a single character.")
        self.blank = blank
        self._cells: Dict[int, str] = {}
        self.head = 0                      # head position, independent of contents
        self._min_pos = 0                  # leftmost position ever occupied
        self._max_pos = 0                  # rightmost position ever occupied
        self.load(contents)

    # ------------------------------------------------------------------ setup
    def load(self, contents: Iterable[str]) -> None:
        """Place `contents` at positions 0, 1, 2, ... and put the head on 0."""
        symbols = tuple(contents)
        self._cells = {}
        for pos, sym in enumerate(symbols):
            if len(sym) != 1:
                raise ValueError(f"Tape symbols must be single characters, got {sym!r}.")
            if sym != self.blank:
                self._cells[pos] = sym
        self.head = 0
        self._min_pos = 0
        self._max_pos = max(len(symbols) - 1, 0)

    # --------------------------------------------------------------- access
    def read(self) -> str:
        """Symbol under the head (blank if the cell was never written)."""
        return self._cells.get(self.head, self.blank)

    def cell(self, position: int) -> str:
        """Symbol at an arbitrary position."""
        return self._cells.get(position, self.blank)

    def write(self, symbol: str) -> None:
        """Write `symbol` at the head position."""
        if len(symbol) != 1:
            raise ValueError(f"Tape symbols must be single characters, got {symbol!r}.")
        if symbol == self.blank:
            self._cells.pop(self.head, None)
        else:
            self._cells[self.head] = symbol

    def move(self, direction: str) -> None:
        """Move the head one cell left or right."""
        if direction == LEFT:
            self.head -= 1
        elif direction == RIGHT:
            self.head += 1
        else:
            raise ValueError(f"Direction must be 'L' or 'R', got {direction!r}.")
        self._min_pos = min(self._min_pos, self.head)
        self._max_pos = max(self._max_pos, self.head)

    # ------------------------------------------------------------ inspection
    def snapshot(self) -> Tuple[Tuple[int, str], ...]:
        """Immutable, sorted copy of all non-blank cells: ((pos, symbol), ...)."""
        return tuple(sorted(self._cells.items()))

    def bounds(self) -> Tuple[int, int]:
        """(lowest, highest) position that the input or the head has occupied."""
        return self._min_pos, self._max_pos

    def as_string(self, low: Optional[int] = None, high: Optional[int] = None) -> str:
        """Render positions low..high (inclusive) as a string, blanks included."""
        lo, hi = self.bounds()
        low = lo if low is None else low
        high = hi if high is None else high
        return "".join(self.cell(p) for p in range(low, high + 1))
