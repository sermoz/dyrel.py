from typing import Optional

from dyrel.util import Slotted_Class


class Snapshot(metaclass=Slotted_Class):
    added: set
    removed: set
    next: Optional["Snapshot"]

    def __init__(self):
        self.added = set()
        self.removed = set()
        self.next = None

    @property
    def is_clean(self):
        return not self.added and not self.removed

    @property
    def is_most_recent(self):
        return self.next is None

    def add(self, record):
        if record in self.removed:
            self.removed.remove(record)
        else:
            self.added.add(record)

    def remove(self, record):
        if record in self.added:
            self.added.remove(record)
        else:
            self.removed.add(record)

    def unchain(self):
        if self.is_most_recent:
            return

        unchain(self)


def unchain(snapshot):
    """Unchain the given snapshot which should not to be the most recent one."""
    next_one = snapshot.next

    if next_one.is_most_recent:
        return  # this is the definition of "unchained"

    unchain(next_one)

    A, R = snapshot.added, snapshot.removed
    An, Rn = next_one.added, next_one.removed

    pA = An - R
    pR = Rn - A

    A -= Rn
    A |= pA

    R -= An
    R |= pR

    snapshot.next = next_one.next
