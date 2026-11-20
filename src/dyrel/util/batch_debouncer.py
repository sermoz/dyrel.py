import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass(eq=False, repr=False, slots=True)
class BatchDebouncer:
    """A debouncer for source file-related FS events.

    Accumulates a set of dirty file paths.
    """

    MAX_WAIT: ClassVar[float] = 2.0  # wait no more than that after the first change
    QUIET: ClassVar[float] = 0.5  # if no changes during that long, issue a reload

    dirty: set
    first: float | None
    timer: asyncio.TimerHandle | None
    ready: asyncio.Event

    def __init__(self):
        self.dirty = set()
        self.first = None
        self.timer = None
        self.ready = asyncio.Event()

    def add(self, item):
        self.dirty.add(item)

        if self.ready.is_set():
            return

        now = asyncio.get_running_loop().time()
        if self.first is None:
            self.first = now
        if self.timer:
            self.timer.cancel()

        remaining_wait = self.first + self.MAX_WAIT - now
        trigger_in = max(0.0, min(remaining_wait, self.QUIET))
        self.timer = asyncio.get_running_loop().call_later(trigger_in, self.ready.set)

    async def get_batch(self) -> set:
        await self.ready.wait()
        dirty = set(self.dirty)

        self.dirty.clear()
        self.first = None
        self.timer = None
        self.ready.clear()

        return dirty
