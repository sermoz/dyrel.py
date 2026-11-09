from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from dyrel.slice import Slice, observe_current_version, unchain_version

if TYPE_CHECKING:
    from dyrel.relation import Record
    from dyrel.slice import Version


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
        if self in STALE_QUERIES:
            STALE_QUERIES.remove(self)
        else:
            self.slyce.unconsume_by(self)


def process_stale_queries():
    while STALE_QUERIES:
        query: Query = STALE_QUERIES.pop()

        breakpoint()
        if query.version is None:
            feed_to_query(query, query.slyce.records, added=True)
        else:
            unchain_version(query.version)

            feed_to_query(query, query.version.gone, added=False)
            feed_to_query(query, query.version.came, added=True)

        query.version = observe_current_version(query.slyce)
        query.slyce.consume_by(query)


def feed_to_query(query: Query, recs: Iterable[Record], added: bool):
    for rec in recs:
        query.callback(added, **dict(zip(query.var_names, rec)))
