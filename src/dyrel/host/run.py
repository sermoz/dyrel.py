from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from dyrel import update
from dyrel.host import source
from dyrel.host.inotify import Inotify, Mask
from dyrel.host.load import reload_file, reload_root_dir
from dyrel.util import BatchDebouncer

from .lsp_server import run_lsp_server

if TYPE_CHECKING:
    from dyrel.relation import RelationFactSupport


async def watch_source_files(debouncer: BatchDebouncer):
    with Inotify() as inotify:
        inotify.add_watch(source.ROOT_DIR, Mask.MODIFY)

        async for event in inotify.events():
            debouncer.add(source.ROOT_DIR / event.name)


async def reload_source_files(debouncer: BatchDebouncer):
    while True:
        dirty_files: set[Path] = await debouncer.get_batch()

        rel_deltas: RelationFactSupport = defaultdict(Counter)
        for path in dirty_files:
            reload_file(rel_deltas, path)

        update.apply_delta_facts(rel_deltas)
        update.process_stale_queries()
        print("***")


async def co_main():
    debouncer = BatchDebouncer()

    async with asyncio.TaskGroup() as group:
        group.create_task(watch_source_files(debouncer))
        group.create_task(reload_source_files(debouncer))
        group.create_task(run_lsp_server())

        print("*** Listening for source file changes..")


def main():
    logging.basicConfig(level=logging.INFO, force=False)
    source.ROOT_DIR = Path("sample")

    reload_root_dir()
    # return
    try:
        asyncio.run(co_main())
    except KeyboardInterrupt:
        print("Quitting..")
