from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .inotify import Inotify, Mask


@dataclass(eq=False, repr=False, slots=True)
class Debouncer:
    MAX_WAIT: ClassVar[float] = 2.0   # wait no more than that after the first change
    QUIET: ClassVar[float] = 0.5      # if no changes during that long, issue a reload

    dirty: set[Path]
    first: float | None
    timer: asyncio.TimerHandle | None
    ready: asyncio.Event

    def __init__(self):
        self.dirty = set()
        self.first = None
        self.timer = None
        self.ready = asyncio.Event()

    def mark_dirty(self, file: Path):
        self.dirty.add(file)

        if self.ready.is_set():
            return

        now = asyncio.get_running_loop().time()
        if self.first is None:
            self.first = now
        if self.timer:
            self.timer.cancel()

        remaining_wait = self.first + self.MAX_WAIT - now
        trigger_in = max(.0, min(remaining_wait, self.QUIET))
        self.timer = asyncio.get_running_loop().call_later(trigger_in, self.ready.set)

    async def get_dirty_files(self) -> set[Path]:
        await self.ready.wait()
        dirty = set(self.dirty)

        self.dirty.clear()
        self.first = None
        self.timer = None
        self.ready.clear()

        return dirty


async def watch_source_files(debouncer):
    with Inotify() as inotify:
        inotify.add_watch("sample", Mask.MODIFY)

        async for event in inotify.events():
            debouncer.mark_dirty(Path("sample") / event.name)


async def keep_engine_up_to_date(debouncer):
    while True:
        dirty_files = await debouncer.get_dirty_files()

        # You stopped here: implement file comparison and reloading
        print("Got these dirty files:", dirty_files)


async def run():
    debouncer = Debouncer()

    async with asyncio.TaskGroup() as group:
        group.create_task(watch_source_files(debouncer))
        group.create_task(keep_engine_up_to_date(debouncer))


def main():
    asyncio.run(run())
