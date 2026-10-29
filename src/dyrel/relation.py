from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeAlias, cast

from .exc import DyrelError

RELATION_REGISTRY: dict[str, Relation] = {}


@dataclass(eq=False, slots=True)
class Relation:
    signature: str
    arity: int
    records: Counter[Record] = field(default_factory=Counter, init=False)

    def __repr__(self):
        return f'#{self.signature}'


Record: TypeAlias = tuple


class RObject:
    """The "r" object (`from dyrel import r`): relation builder."""
    is_link_root: ClassVar[bool] = True

    def __getattr__(self, name):
        return RelAppLink(prev=self, name=name)

    def __iadd__(self, chain: RelAppLink):
        from dyrel.loader import cur_file_facts

        if cur_file_facts is None:
            raise DyrelError('"r += ..." in a context where it\'s not expected')

        app = RelApp.from_chain(chain)

        if not app.is_ground:
            raise DyrelError("We cannot yet define rules, only ground facts")

        cur_file_facts[app.rel][tuple(cast(Val, val).value for val in app.args)] += 1

        return self


@dataclass(eq=False, frozen=True, slots=True)
class RelAppLink:
    _prev: RelAppLink | RObject
    _name: str
    _arg: Val | Var | None = None

    is_link_root: ClassVar[bool] = False

    def __init__(self, prev, name, arg=None):
        object.__setattr__(self, "_prev", prev)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_arg", arg)

    def __getattr__(self, name):
        return RelAppLink(self, name)

    def __call__(self, obj):
        if self._arg is not None:
            raise DyrelError("Ill-formed relation application (a call following another call)")

        return RelAppLink(
            prev=self._prev,
            name=self._name,
            arg=obj if isinstance(obj, Var) else Val(obj)
        )


@dataclass(eq=True, frozen=True, slots=True)
class Val:
    value: Any

    def matches(self, v) -> bool:
        return self.value == v


@dataclass(eq=True, frozen=True, slots=True)
class Var:
    name: str

    def matches(self, v) -> bool:
        return True


def chain_relation(chain: RelAppLink) -> Relation:
    signature = chain_signature(chain)
    relation = RELATION_REGISTRY.get(signature)

    if relation is None:
        relation = RELATION_REGISTRY[signature] = Relation(
            signature=signature,
            arity=chain_arity(chain),
        )

    return relation


def chain_signature(chain: RelAppLink) -> str:
    """Get relation signature (a string) corresponding to the given chain"""
    assert not chain.is_link_root

    parts = [chain._name + (":" if chain._arg else "")]
    link = chain._prev

    while not link.is_link_root:
        parts.append(link._name + (":" if link._arg else "."))
        link = link._prev

    parts.reverse()

    return "".join(parts)


def chain_arity(chain: RelAppLink) -> int:
    arity = 0
    link = chain

    while not link.is_link_root:
        arity += 1
        link = link._prev

    return arity


def chain_args(chain: RelAppLink) -> tuple:
    args = []
    link = chain

    while not link.is_link_root:
        if link._arg is not None:
            args.append(link._arg)
        link = link._prev

    return tuple(args[::-1])


class VObject:
    """The "v" object (`from dyrel import v`)."""
    def __getattr__(self, name):
        return Var(name)


@dataclass(eq=True, frozen=True, slots=True)
class RelApp:
    rel: Relation
    args: tuple[Var | Val, ...]

    @classmethod
    def from_chain(cls, chain: RelAppLink) -> RelApp:
        return RelApp(
            rel=chain_relation(chain),
            args=chain_args(chain),
        )

    @property
    def is_ground(self):
        return all(isinstance(arg, Val) for arg in self.args)

    def is_satisfied_by_record(self, rec: tuple) -> bool:
        assert len(self.args) == len(rec), "Record length does not match"

        return all(arg.matches(v) for arg, v in zip(self.args, rec))


def root(name, chain: RelAppLink):
    from dyrel.loader import Query, cur_file_queries

    if cur_file_queries is None:
        raise DyrelError('"root()" in a context where it\'s not expected')

    cur_file_queries.add(Query(name, RelApp.from_chain(chain)))
