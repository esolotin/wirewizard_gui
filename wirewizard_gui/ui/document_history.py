from __future__ import annotations

from copy import deepcopy
from typing import Callable

from PySide6.QtGui import QUndoCommand


class ProjectSnapshotCommand(QUndoCommand):
    def __init__(
        self,
        text: str,
        before: dict,
        after: dict,
        restore: Callable[[dict], None],
    ) -> None:
        super().__init__(text)
        self._before = deepcopy(before)
        self._after = deepcopy(after)
        self._restore = restore
        self._initial_redo = True

    def undo(self) -> None:
        self._restore(self._before)

    def redo(self) -> None:
        if self._initial_redo:
            self._initial_redo = False
            return
        self._restore(self._after)
