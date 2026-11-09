from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from typing_extensions import Sentinel

from dyrel.dsl import Var

if TYPE_CHECKING:
    from dyrel.query import Query
    from dyrel.relation import Record, RelApp, Relation


@dataclass(eq=False, repr=False, slots=True)
class Slice:
    rel: Relation
    mask: SliceMask
    arity: int  # number of 'FREE_ARG's in 'mask'
    records: Counter[Record]
    latest_version: Version | None
    valid_consumers: set[Query]  # currently only Queries can depend on slices
    consumers: set[Query]  # temp solution, we really need GC

    def __init__(self, rel: Relation, mask: SliceMask):
        self.rel = rel
        self.mask = mask
        self.arity = slice_mask_arity(mask)
        self.records = Counter()
        self.latest_version = None
        self.valid_consumers = set()
        self.consumers = set()

    def consume_by(self, query: Query):
        self.consumers.add(query)
        self.valid_consumers.add(query)

    def unconsume_by(self, query: Query):
        self.consumers.remove(query)
        self.valid_consumers.discard(query)

        if not self.consumers:
            self.latest_version = None

    def consumer_invalidated(self, query: Query):
        self.valid_consumers.remove(query)


class SliceMask(tuple):
    """Tuple of unwrapped values or FREE_ARGS"""

    __slots__ = ()


FREE_ARG = Sentinel("*")


def slice_mask_by_rel_app(rel_app: RelApp) -> SliceMask:
    """Treat all the variables in 'rel_app' as wildcards. Don't check for dups."""
    return SliceMask(
        FREE_ARG if isinstance(arg, Var) else arg.value for arg in rel_app.args
    )


def slice_mask_arity(mask: SliceMask) -> int:
    return sum(1 for item in mask if item is FREE_ARG)


def slice_for_mask(rel: Relation, mask: SliceMask) -> Slice:
    """Intern the slice and return it."""
    if (slyce := rel.slices.get(mask)) is None:
        slyce = rel.slices[mask] = Slice(rel, mask)

    return slyce


def slice_for_rel_app(app: RelApp) -> Slice:
    """Return a Slice designated by 'app'.

    Ignore var duplicates: all vars are treated as wildcards, independent of names.
    """
    return slice_for_mask(app.rel, slice_mask_by_rel_app(app))


def slice_mask_match_fact(mask: SliceMask, fact: Record) -> list | None:
    assert len(mask) == len(fact), "Arity mismatch"

    bindings = []

    for m, f in zip(mask, fact):
        if m is FREE_ARG:
            bindings.append(f)
        elif m == f:
            pass
        else:
            return None

    return bindings


def invalidate(slyce: Slice):
    queries = list(slyce.valid_consumers)
    slyce.valid_consumers.clear()
    for query in queries:
        query.invalidate()


def slice_delta_record(slyce: Slice, rec: Record, d_sup: int):
    """Change thte given record's support count in this slice.

    Reflect the change in the .latest_version, too.
    """
    assert d_sup != 0

    o_sup = slyce.records[rec]
    n_sup = o_sup + d_sup

    assert n_sup >= 0

    if slyce.latest_version:
        if o_sup == 0:
            slyce.latest_version.record_came(rec)
            invalidate(slyce)
        elif n_sup == 0:
            slyce.latest_version.record_gone(rec)
            invalidate(slyce)

    if n_sup == 0:
        del slyce.records[rec]
    else:
        slyce.records[rec] = n_sup


@dataclass(eq=False, repr=False, slots=True)
class Version:
    next: Version | None
    came: set[Record]
    gone: set[Record]

    def __init__(self):
        self.next = None
        self.came = set()
        self.gone = set()

    @property
    def is_clean(self) -> bool:
        return not self.came and not self.gone

    def record_came(self, rec: Record):
        if rec in self.gone:
            self.gone.remove(rec)
        else:
            assert rec not in self.came, "Cannot add same record twice"
            self.came.add(rec)

    def record_gone(self, rec: Record):
        if rec in self.came:
            self.came.remove(rec)
        else:
            assert rec not in self.gone, "Cannot remove same record twice"
            self.gone.add(rec)


def observe_current_version(slyce: Slice) -> Version:
    if slyce.latest_version is None:
        slyce.latest_version = Version()
        return slyce.latest_version

    if slyce.latest_version.is_clean:
        return slyce.latest_version

    new_latest = Version()
    slyce.latest_version.next = new_latest
    slyce.latest_version = new_latest

    return slyce.latest_version


def unchain_version(version: Version):
    if version.next is None:
        return

    unchain_version(version.next)

    # Between two consecutive versions there can be items that cancel each other out.
    cancel_out = (version.came & version.next.gone) | (version.gone & version.next.came)

    version.came = (version.came | version.next.came) - cancel_out
    version.gone = (version.gone | version.next.gone) - cancel_out

    version.next = None
