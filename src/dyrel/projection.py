from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from dyrel.datum import Datum
from dyrel.engine import processing_queue
from dyrel.snapshot import Snapshot
from dyrel.util import Slotted_Class, Stub, init_with_kwargs, member_of
from dyrel.variable import Variable

if TYPE_CHECKING:
    from dyrel.relation import Relation


WILDCARD = Stub("*")


@member_of(Datum)
def _as_projection_coords(self):
    return tuple(
        WILDCARD if isinstance(value, Variable) else value
        for value in self._values()
    )


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

    __init__ = init_with_kwargs

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
