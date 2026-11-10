from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from dyrel.dsl import Val, Var, chain_args, chain_arity, chain_signature
from dyrel.slice import slice_delta_record, slice_mask_match_fact

if TYPE_CHECKING:
    from dyrel.dsl import RelAppLink
    from dyrel.slice import Slice, SliceMask


RELATION_REGISTRY: dict[str, Relation] = {}


@dataclass(eq=False, slots=True)
class Relation:
    signature: str
    arity: int
    # We only support facts for now, i.e. rules without bodies. Every fact can be defined
    # more than once, generally speaking (support count).
    facts: Counter[Record] = field(default_factory=Counter, init=False)
    slices: dict[SliceMask, Slice] = field(default_factory=dict, init=False)

    def __repr__(self):
        return f"#<{self.signature}>"


class Record(tuple):
    __slots__ = ()


@dataclass(eq=True, repr=False, slots=True)
class RelApp:
    rel: Relation
    args: tuple[Var | Val, ...]

    @classmethod
    def from_chain(cls, chain: RelAppLink) -> RelApp:
        return RelApp(
            rel=relation_for_chain(chain),
            args=chain_args(chain),
        )

    @property
    def is_ground(self):
        return all(isinstance(arg, Val) for arg in self.args)

    @property
    def var_names(self) -> tuple[str, ...]:
        return tuple(var.name for var in self.args if isinstance(var, Var))

    def is_satisfied_by_record(self, rec: tuple) -> bool:
        assert len(self.args) == len(rec), "Record length does not match"

        return all(arg.matches(v) for arg, v in zip(self.args, rec))


def relation_for_chain(chain: RelAppLink) -> Relation:
    signature = chain_signature(chain)
    relation = RELATION_REGISTRY.get(signature)

    if relation is None:
        relation = RELATION_REGISTRY[signature] = Relation(
            signature=signature,
            arity=chain_arity(chain),
        )

    return relation


RelationFactSupport: TypeAlias = defaultdict[Relation, Counter[Record]]


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

                bindings = slice_mask_match_fact(slyce.mask, fact)
                if bindings is not None:
                    slice_delta_record(slyce, Record(bindings), d_sup)
