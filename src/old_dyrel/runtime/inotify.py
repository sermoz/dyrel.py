from __future__ import annotations

import ctypes
import enum
import os
from struct import Struct

from dyrel import util

libc = ctypes.CDLL("libc.so.6", use_errno=True)


def error_handler(result, func, arguments):
    if result == -1:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))

    return result


libc.inotify_init1.errcheck = error_handler
libc.inotify_add_watch.errcheck = error_handler
libc.inotify_rm_watch.errcheck = error_handler


class Inotify:
    fd: int

    __slots__ = tuple(__annotations__)

    def __init__(self):
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)

    def close(self):
        os.close(self.fd)
        self.fd = None

    def add_watch(self, path, mask) -> int:
        return libc.inotify_add_watch(self.fd, os.fsencode(path), mask)

    def remove_watch(self, wd):
        libc.inotify_rm_watch(self.fd, wd)


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


class Event:
    wd: int
    mask: Mask
    cookie: int
    name: str

    __slots__ = tuple(__annotations__)
    __init__ = util.keyword_initializer_for(__slots__)

    def __repr__(self):
        return f"#<wd={self.wd}, mask={repr(self.mask)}, cookie={self.cookie}, name=\"{self.name}\">"


EVENT_FORMAT = Struct('iIII')


def unpack_events(data: bytes) -> list[Event]:
    """Unpack any number of events from the given bytes object"""
    pos = 0
    events = []

    while pos < len(data):
        wd, mask, cookie, namesize = EVENT_FORMAT.unpack_from(data, pos)
        pos += EVENT_FORMAT.size

        end = data.index(b'\x00', pos, pos + namesize)
        name = os.fsdecode(data[pos:end])
        pos += namesize

        events.append(Event(wd=wd, mask=Mask(mask), cookie=cookie, name=name))

    return events
