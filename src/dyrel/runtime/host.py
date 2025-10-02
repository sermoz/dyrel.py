import ctypes
import fcntl
import os
import select
import sys
import termios

from .inotify import Inotify, Mask, unpack_events


def main():
    inotify = Inotify()
    wd = inotify.add_watch("sample", Mask.MODIFY)

    poll = select.poll()
    poll.register(inotify.fd)

    try:
        while True:
            poll.poll()

            avail = ctypes.c_int()
            fcntl.ioctl(inotify.fd, termios.FIONREAD, avail)

            if avail.value == 0:
                print("No bytes available, polling again..")
                continue

            data = os.read(inotify.fd, avail.value)
            events = unpack_events(data)

            for event in events:
                print(event)
    finally:
        inotify.remove_watch(wd)


if __name__ == "__main__":
    main()
    sys.exit(0)
