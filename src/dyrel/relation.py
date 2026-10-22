from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from typing import ClassVar

from .exc import DyrelError


class R_Object:
    is_link_root: ClassVar[bool] = True

    def __getattr__(self, name):
        return Rel_App_Link(prev=self, name=name)

    def __iadd__(self, chain: Rel_App_Link):
        signature = chain_signature(chain)
        relation = relation_registry.get(signature)

        if relation is None:
            relation = relation_registry[signature] = Relation(
                signature=signature,
                arity=chain_arity(chain),
            )

        values = chain_values(chain)
        relation.facts.append(values)

        return self


@dataclass(eq=False, frozen=True, slots=True)
class Rel_App_Link:
    _prev: Rel_App_Link | R_Object
    _name: str
    _arg: Val | None = None

    is_link_root: ClassVar[bool] = False

    def __init__(self, prev, name, arg=None):
        object.__setattr__(self, "_prev", prev)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_arg", arg)

    def __getattr__(self, name):
        return Rel_App_Link(self, name)

    def __call__(self, val):
        if self._arg is not None:
            raise DyrelError("Ill-formed relation application (a call following another call)")

        return Rel_App_Link(prev=self._prev, name=self._name, arg=Val(val))


@dataclass(eq=False, frozen=True, slots=True)
class Val:
    val: Any


def chain_signature(chain: Rel_App_Link) -> str:
    """Get relation signature (a string) corresponding to the given chain"""
    assert not chain.is_link_root

    parts = [chain._name + (":" if chain._arg else "")]
    link = chain._prev

    while not link.is_link_root:
        parts.append(link._name + (":" if link._arg else "."))
        link = link._prev

    parts.reverse()

    return "".join(parts)


def chain_arity(chain: Rel_App_Link) -> int:
    arity = 0
    link = chain

    while not link.is_link_root:
        arity += 1
        link = link._prev

    return arity


def chain_values(chain: Rel_App_Link) -> tuple:
    values = []
    link = chain

    while not link.is_link_root:
        if link._arg:
            values.append(link._arg.val)
        link = link._prev

    return tuple(values[::-1])


relation_registry: dict[str, Relation] = {}


@dataclass(eq=False, frozen=False, slots=True)
class Relation:
    signature: str
    arity: int
    facts: list[tuple] = field(default_factory=list)

