from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from dyrel import update
from dyrel.load import reload_dir, reload_file

from .inotify import Inotify, Mask
from .lsp_server import run_lsp_server

if TYPE_CHECKING:
    from dyrel.relation import RelationFactSupport


@dataclass(eq=False, repr=False, slots=True)
class DirtyFileDebouncer:
    """A debouncer for source file-related FS events.

    Accumulates a set of dirty file paths.
    """

    MAX_WAIT: ClassVar[float] = 2.0  # wait no more than that after the first change
    QUIET: ClassVar[float] = 0.5  # if no changes during that long, issue a reload

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
        trigger_in = max(0.0, min(remaining_wait, self.QUIET))
        self.timer = asyncio.get_running_loop().call_later(trigger_in, self.ready.set)

    async def get_dirty_files(self) -> set[Path]:
        await self.ready.wait()
        dirty = set(self.dirty)

        self.dirty.clear()
        self.first = None
        self.timer = None
        self.ready.clear()

        return dirty


async def watch_source_files(debouncer: DirtyFileDebouncer):
    with Inotify() as inotify:
        inotify.add_watch("sample", Mask.MODIFY)

        async for event in inotify.events():
            debouncer.mark_dirty(Path("sample") / event.name)


async def reload_source_files(debouncer: DirtyFileDebouncer):
    while True:
        dirty_files = await debouncer.get_dirty_files()

        rel_deltas: RelationFactSupport = defaultdict(Counter)

        for path in dirty_files:
            # print(f'Reloading file: "{path}"')
            reload_file(rel_deltas, path)

        update.apply_delta_facts(rel_deltas)
        update.process_stale_queries()
        print("***")


async def run():
    debouncer = DirtyFileDebouncer()

    async with asyncio.TaskGroup() as group:
        group.create_task(watch_source_files(debouncer))
        group.create_task(reload_source_files(debouncer))
        group.create_task(run_lsp_server())

        print("*** Listening for source file changes..")


def main():
    logging.basicConfig(level=logging.INFO, force=False)

    reload_dir(Path("sample"))

    # return
    asyncio.run(run())
