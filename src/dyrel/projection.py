from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from dyrel.datum import Datum
from dyrel.defs import WILDCARD
from dyrel.engine import processing_queue
from dyrel.snapshot import Snapshot
from dyrel.util import Slotted_Class, member_of
from dyrel.variable import Variable

if TYPE_CHECKING:
    from dyrel.relation import Relation



@member_of(Datum)
def _values(self):
    return (seg.value for seg in self._segments if seg.is_bearing)


@member_of(Datum)
def _as_record(self):
    return tuple(self._values())


@member_of(Datum)
def _as_projection_coords(self):
    return tuple(
        WILDCARD if isinstance(value, Variable) else value
        for value in self._values()
    )


@member_of(Datum)
def _variable_names(self):
    return tuple(var.name for var in self._values() if isinstance(var, Variable))


class Projection(metaclass=Slotted_Class):
    relation: "Relation"
    coords: tuple
    records: set
    most_recent_snapshot: Optional["Snapshot"]
    observers: set
    clean_observers: set

    def __init__(self, relation, coords):
        self.relation = relation
        self.coords = coords
        self.records = set()
        self.most_recent_snapshot = None
        self.observers = set()
        self.clean_observers = set()

    def add_observer(self, on_add, on_remove):
        observer = Observer(
            proj=self,
            snapshot=None,
            on_add=on_add,
            on_remove=on_remove,
        )

        self.observers.add(observer)
        processing_queue.add(observer)

        return observer

    def remove_observer(self, observer):
        self.observers.remove(observer)
        self.clean_observers.discard(observer)

        if not self.observers:
            self.most_recent_snapshot = None

    def restore_clean_observer(self, observer):
        assert observer in self.observers

        self.clean_observers.add(observer)

    def get_current_snapshot(self):
        if self.most_recent_snapshot is None:
            self.most_recent_snapshot = Snapshot()
        elif not self.most_recent_snapshot.is_clean:
            self.most_recent_snapshot.next = self.most_recent_snapshot = Snapshot()

        return self.most_recent_snapshot

    def try_to_fill_by(self, clause):
        if not self.covers(clause.head_record):
            return

        # TODO: continue here

    def consider_adding(self, full_record):
        # 'full_record' here is a ground datum representing the clause head.
        if not self.covers(full_record):
            return

        record = tuple(R for C, R in zip(self.coords, full_record) if C is WILDCARD)
        self.records.add(record)

        if self.most_recent_snapshot is not None:
            self.most_recent_snapshot.add(record)
            if self.clean_observers:
                processing_queue.add_all(self.clean_observers)
                self.clean_observers.clear()

    def covers(self, full_record) -> bool:
        return all(C is WILDCARD or C == R for C, R in zip(self.coords, full_record))


class Observer(metaclass=Slotted_Class):
    proj: "Projection"
    snapshot: "Snapshot"
    on_add: Callable
    on_remove: Callable

    def revalidate(self):
        current_snapshot = self.proj.get_current_snapshot()

        if self.snapshot is None:
            # The snapshot is logically a zero/initial one (no data at all)
            for rec in self.proj.records:
                self.on_add(rec)
        else:
            self.snapshot.unchain()

            for rec in self.snapshot.removed:
                self.on_remove(rec)

            for rec in self.snapshot.added:
                self.on_add(rec)

        self.snapshot = current_snapshot
        self.proj.restore_clean_observer(self)


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
    """Unchain the given snapshot which should not be the most recent one."""
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
