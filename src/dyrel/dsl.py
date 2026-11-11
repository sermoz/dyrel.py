from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from dyrel.exc import DyrelError


class RObject:
    """The "r" object (`from dyrel import r`): relation builder."""

    is_link_root: ClassVar[bool] = True

    def __getattr__(self, name):
        return RelAppLink(prev=self, name=name)

    def __iadd__(self, chain: RelAppLink):
        from dyrel.load import register_fact

        register_fact(chain)
        return self


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


class VObject:
    """The "v" object (`from dyrel import v`)."""

    def __getattr__(self, name):
        return Var(name)


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
            raise DyrelError(
                "Ill-formed relation application (a call following another call)"
            )

        return RelAppLink(
            prev=self._prev,
            name=self._name,
            arg=obj if isinstance(obj, Var) else Val(obj),
        )


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
