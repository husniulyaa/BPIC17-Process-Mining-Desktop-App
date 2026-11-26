"""Centralized background task load-balancer to prevent GIL contention & OOM crashes.

When a large event log (e.g., BPIC17 with 1.2M events) is loaded, running
multiple heavy Pandas workers simultaneously causes Python GIL starvation
('Not Responding' window freezes) and multi-GB memory spikes.

``TaskScheduler`` serializes heavy background tasks through a single worker
thread with LIFO priority so whichever tab the user is currently viewing runs
first while keeping the Qt GUI event loop responsive.
"""

from __future__ import annotations

from collections import OrderedDict
import gc
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class _RunnerThread(QThread):
    task_succeeded = Signal(str, int, object)
    task_failed = Signal(str, int, str)

    def __init__(
        self,
        key: str,
        generation: int,
        fn: Callable[[], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.generation = generation
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.task_succeeded.emit(self.key, self.generation, result)
        except Exception as exc:  # noqa: BLE001
            self.task_failed.emit(self.key, self.generation, str(exc))


class TaskScheduler(QObject):
    """Single-concurrency LIFO priority scheduler for heavy DataFrame analyses."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._generation: int = 0
        self._queue: OrderedDict[
            str,
            tuple[
                int,
                Callable[[], Any],
                Callable[[Any], None],
                Callable[[str], None],
            ],
        ] = OrderedDict()
        self._active_runner: _RunnerThread | None = None

    @property
    def generation(self) -> int:
        return self._generation

    def reset_generation(self) -> int:
        """Invalidate all pending/in-flight tasks when a new dataset is loaded."""
        self._generation += 1
        self._queue.clear()
        gc.collect()
        return self._generation

    def submit(
        self,
        key: str,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None],
        *,
        high_priority: bool = True,
    ) -> None:
        """Schedule ``fn`` under ``key``, replacing any older queued task for ``key``."""
        if key in self._queue:
            del self._queue[key]
        self._queue[key] = (self._generation, fn, on_success, on_error)
        if high_priority:
            # Move to end; we pop from end (LIFO) so the user's active tab runs next!
            self._queue.move_to_end(key, last=True)
        self._pump()

    def _pump(self) -> None:
        if self._active_runner is not None or not self._queue:
            return

        key, (gen, fn, on_success, on_error) = self._queue.popitem(last=True)
        if gen != self._generation:
            self._pump()
            return

        runner = _RunnerThread(key, gen, fn, self)
        self._callbacks = (on_success, on_error)
        runner.task_succeeded.connect(self._on_succeeded)
        runner.task_failed.connect(self._on_failed)
        runner.finished.connect(self._on_finished)
        runner.finished.connect(runner.deleteLater)
        self._active_runner = runner
        runner.start()

    def _on_succeeded(self, _key: str, gen: int, result: Any) -> None:
        if gen == self._generation and hasattr(self, "_callbacks"):
            on_success, _ = self._callbacks
            on_success(result)

    def _on_failed(self, _key: str, gen: int, message: str) -> None:
        if gen == self._generation and hasattr(self, "_callbacks"):
            _, on_error = self._callbacks
            on_error(message)

    def _on_finished(self) -> None:
        self._active_runner = None
        self._pump()


GLOBAL_TASK_SCHEDULER = TaskScheduler()

__all__ = ["GLOBAL_TASK_SCHEDULER", "TaskScheduler"]
