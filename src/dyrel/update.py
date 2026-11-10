from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from dyrel.relation import STALE_QUERIES, Record

if TYPE_CHECKING:
    from dyrel.relation import Query, RelationFactSupport, Slice


def process_stale_queries():
    while STALE_QUERIES:
        query: Query = STALE_QUERIES.pop()

        if query.version is None:
            query.slyce.ensure_filled()
            feed_to_query(query, query.slyce.records, added=True)
        else:
            query.version.ensure_unchained()

            feed_to_query(query, query.version.gone, added=False)
            feed_to_query(query, query.version.came, added=True)

        query.version = query.slyce.get_current_version()
        query.slyce.consume_by(query)


def feed_to_query(query: Query, recs: Iterable[Record], added: bool):
    for rec in recs:
        query.callback(added, **dict(zip(query.var_names, rec)))


def invalidate_slice(slyce: Slice):
    queries = list(slyce.valid_consumers)
    slyce.valid_consumers.clear()
    for query in queries:
        query.invalidate()


def slice_delta_record(slyce: Slice, rec: Record, d_sup: int):
    """Change the given record's support count in this slice.

    Reflect the change in the .latest_version, too.
    """
    assert d_sup != 0

    o_sup = slyce.records[rec]
    n_sup = o_sup + d_sup

    assert n_sup >= 0

    if slyce.latest_version:
        if o_sup == 0:
            slyce.latest_version.record_came(rec)
            invalidate_slice(slyce)
        elif n_sup == 0:
            slyce.latest_version.record_gone(rec)
            invalidate_slice(slyce)

    if n_sup == 0:
        del slyce.records[rec]
    else:
        slyce.records[rec] = n_sup


def apply_delta_facts(rel_deltas: RelationFactSupport):
    """Update all the consumers (slice) to reflect the changed producers (facts).

    The deltas in 'rel_deltas' may come non-normalized (has 0s).
    """
    for rel, delta in rel_deltas.items():
        for fact, d_sup in delta.items():
            if d_sup == 0:
                continue

            rel.facts[fact] += d_sup
            if rel.facts[fact] == 0:
                del rel.facts[fact]

            for slyce in rel.slices.values():
                if slyce.is_unfilled:
                    continue

                if (bindings := slyce.mask.match_fact(fact)) is not None:
                    slice_delta_record(slyce, Record(bindings), d_sup)
