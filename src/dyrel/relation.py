from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from typing_extensions import Sentinel

from dyrel.dsl import Val, Var, chain_args, chain_arity, chain_signature

if TYPE_CHECKING:
    from dyrel.dsl import RelAppLink


class Record(tuple):
    """Record is either a fact (in a relation) or just a record (in a slice)."""

    __slots__ = ()


RELATION_REGISTRY: dict[str, Relation] = {}


@dataclass(eq=False, slots=True)
class Relation:
    signature: str
    arity: int
    # We only support facts for now, i.e. rules without bodies. Every fact can be defined
    # more than once, generally speaking (support count).
    facts: Counter[Record]
    slices: dict[SliceMask, Slice]

    def __init__(self, signature: str, arity: int):
        self.signature = signature
        self.arity = arity
        self.facts = Counter()
        self.slices = {}

    def __repr__(self):
        return f"#<{self.signature}>"

    @staticmethod
    def by_chain(chain: RelAppLink) -> Relation:
        signature = chain_signature(chain)

        if (relation := RELATION_REGISTRY.get(signature)) is None:
            relation = RELATION_REGISTRY[signature] = Relation(
                signature, chain_arity(chain)
            )

        return relation

    def slice_for_mask(self, mask: SliceMask) -> Slice:
        """Intern the slice and return it."""
        if (slyce := self.slices.get(mask)) is None:
            slyce = self.slices[mask] = Slice(self, mask)
            UNFILLED_SLICES.add(slyce)

        return slyce


@dataclass(eq=True, repr=False, slots=True)
class RelApp:
    rel: Relation
    args: tuple[Var | Val, ...]

    @classmethod
    def from_chain(cls, chain: RelAppLink) -> RelApp:
        return RelApp(rel=Relation.by_chain(chain), args=chain_args(chain))

    @property
    def is_ground(self):
        return all(isinstance(arg, Val) for arg in self.args)

    @property
    def var_names(self) -> tuple[str, ...]:
        return tuple(var.name for var in self.args if isinstance(var, Var))


# This is how we represent fact support counts for multiple relations, and also the delta
# of it.
RelationFactSupport: TypeAlias = defaultdict[Relation, Counter[Record]]


# When a slice is created, it's put here. Then it's fully initialized on first use and
# then kept up-to-date.
UNFILLED_SLICES: set[Slice] = set()


@dataclass(eq=False, repr=False, slots=True)
class Slice:
    rel: Relation
    mask: SliceMask
    arity: int  # number of 'FREE_ARG's in 'mask'
    records: Counter[Record]  # None means not yet initialized
    latest_version: Version | None
    valid_consumers: set[Query]  # currently only Queries can depend on slices
    consumers: set[Query]  # temp solution, we really need GC

    def __init__(self, rel: Relation, mask: SliceMask):
        self.rel = rel
        self.mask = mask
        self.arity = mask.arity
        self.records = Counter()
        self.latest_version = None
        self.valid_consumers = set()
        self.consumers = set()

    @staticmethod
    def for_rel_app(app: RelApp) -> Slice:
        """Return a Slice designated by 'app'.

        Ignore var duplicates: all vars are treated as wildcards, independent of names.
        """
        return app.rel.slice_for_mask(SliceMask.by_rel_app(app))

    @property
    def is_unfilled(self) -> bool:
        return self in UNFILLED_SLICES

    def consume_by(self, query: Query):
        self.consumers.add(query)
        self.valid_consumers.add(query)

    def unconsume_by(self, query: Query):
        self.consumers.remove(query)
        self.valid_consumers.discard(query)

        if not self.consumers:
            self.latest_version = None

    def ensure_filled(self):
        if self not in UNFILLED_SLICES:
            return

        for fact, sup in self.rel.facts.items():
            if (bindings := self.mask.match_fact(fact)) is not None:
                self.records[Record(bindings)] += sup

        UNFILLED_SLICES.remove(self)

    def get_current_version(self: Slice) -> Version:
        if self.latest_version is None:
            self.latest_version = Version()
            return self.latest_version

        if self.latest_version.is_clean:
            return self.latest_version

        new_latest = Version()
        self.latest_version.next = new_latest
        self.latest_version = new_latest

        return self.latest_version


FREE_ARG = Sentinel("*")


class SliceMask(tuple):
    """Tuple of unwrapped values or FREE_ARGS"""

    __slots__ = ()

    @property
    def arity(self) -> int:
        return sum(1 for item in self if item is FREE_ARG)

    @staticmethod
    def by_rel_app(rel_app: RelApp) -> SliceMask:
        """Treat all the variables in 'rel_app' as wildcards. Don't check for dups."""
        return SliceMask(
            FREE_ARG if isinstance(arg, Var) else arg.value for arg in rel_app.args
        )

    def match_fact(self, fact: Record) -> list | None:
        """Match this mask with the given fact.

        :return: a list of bindings corresponding to the free args in self, in order.
        """
        assert len(self) == len(fact), "Arity mismatch"

        bindings = []

        for m, f in zip(self, fact):
            if m is FREE_ARG:
                bindings.append(f)
            elif m == f:
                pass
            else:
                return None

        return bindings


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

    def ensure_unchained(self: Version):
        if self.next is None:
            return

        self.next.ensure_unchained()

        # Between two consecutive versions there can be items that cancel each other out.
        cancel_out = (self.came & self.next.gone) | (self.gone & self.next.came)

        self.came = (self.came | self.next.came) - cancel_out
        self.gone = (self.gone | self.next.gone) - cancel_out

        self.next = None


STALE_QUERIES = set()

# Per a single source file, a query name and the target slice should be unique.
QueryKey: TypeAlias = tuple[str, Slice]


@dataclass(eq=False, repr=False, slots=True)
class Query:
    name: str
    slyce: Slice
    var_names: tuple[str, ...]
    version: Version | None = field(default=None, init=False)
    callback: Callable

    @property
    def key(self) -> QueryKey:
        return self.name, self.slyce

    def invalidate(self):
        STALE_QUERIES.add(self)

    def unlink(self):
        STALE_QUERIES.discard(self)
        self.slyce.unconsume_by(self)
