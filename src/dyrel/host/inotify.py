from __future__ import annotations

import asyncio
import ctypes
import enum
import os
from collections.abc import Iterator
from dataclasses import dataclass
from struct import Struct

libc = ctypes.CDLL("libc.so.6", use_errno=True)


def _check_error(result, func, arguments):
    if result == -1:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))

    return result


libc.inotify_init1.argtypes = [ctypes.c_int]
libc.inotify_init1.restype = ctypes.c_int
libc.inotify_init1.errcheck = _check_error

libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
libc.inotify_add_watch.restype = ctypes.c_int
libc.inotify_add_watch.errcheck = _check_error

libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
libc.inotify_rm_watch.restype = ctypes.c_int
libc.inotify_rm_watch.errcheck = _check_error


class Inotify:
    fd: int
    queue: asyncio.Queue
    watches: list[int]

    def __init__(self):
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        self.queue = asyncio.Queue()
        self.watches = []

        asyncio.get_running_loop().add_reader(self.fd, self._on_readable)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        asyncio.get_running_loop().remove_reader(self.fd)

        while self.watches:
            wd = self.watches.pop()
            libc.inotify_rm_watch(self.fd, wd)

        os.close(self.fd)
        self.fd = -1

        return False

    def add_watch(self, path: str, mask: Mask):
        wd: int = libc.inotify_add_watch(self.fd, os.fsencode(path), mask)
        self.watches.append(wd)

    def _on_readable(self):
        try:
            # The number of bytes doesn't really matter as long as at least 1 inotify
            # event fits in it (~ 272 bytes).
            buffer = os.read(self.fd, 1 << 12)
        except BlockingIOError:
            return

        for event in unpack_events(buffer):
            self.queue.put_nowait(event)

    async def events(self):
        while True:
            yield await self.queue.get()


class Mask(enum.IntFlag):
    # Both 
    ACCESS = 0x1
    MODIFY = 0x2
    ATTRIB = 0x4
    CLOSE_WRITE = 0x8
    CLOSE_NOWRITE = 0x10
    OPEN = 0x20
    MOVED_FROM = 0x40
    MOVED_TO = 0x80
    CREATE = 0x100
    DELETE = 0x200
    DELETE_SELF = 0x400
    MOVE_SELF = 0x800

    ALL_EVENTS = 0xFFF

    MOVE = MOVED_FROM | MOVED_TO
    CLOSE = CLOSE_WRITE | CLOSE_NOWRITE

    # Only mask
    ONLYDIR = 0x1000000
    DONT_FOLLOW = 0x2000000
    EXCL_UNLINK = 0x4000000
    MASK_CREATE = 0x10000000
    MASK_ADD = 0x20000000
    ONESHOT = 0x80000000

    # Only in events
    UNMOUNT = 0x2000
    IGNORED = 0x8000
    Q_OVERFLOW = 0x4000
    ISDIR = 0x40000000


@dataclass(eq=False, frozen=True, slots=True)
class Event:
    wd: int
    mask: Mask
    cookie: int
    name: str


EVENT_FORMAT = Struct('iIII')


def unpack_events(data: bytes) -> Iterator[Event]:
    """Unpack any number of events from the given bytes object"""
    pos = 0

    while pos < len(data):
        wd, mask, cookie, namesize = EVENT_FORMAT.unpack_from(data, pos)
        pos += EVENT_FORMAT.size

        end = data.index(b'\x00', pos, pos + namesize)
        name = os.fsdecode(data[pos:end])
        pos += namesize

        yield Event(wd=wd, mask=Mask(mask), cookie=cookie, name=name)
