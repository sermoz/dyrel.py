from collections.abc import Iterable
from dataclasses import dataclass, field
from weakref import WeakValueDictionary

from dyrel.util import tuplify

signature_registry = WeakValueDictionary()


def get_signature(keys: Iterable[tuple[str, bool]]) -> "Signature":
    keys = tuplify(keys)
    code = signature_code(keys)

    try:
        signature = signature_registry[code]
    except KeyError:
        signature = signature_registry[code] = Signature(keys=keys, code=code)

    return signature


def signature_code(keys: Iterable[tuple[str, bool]]) -> str:
    """Compute the signature code by the signature keys"""

    def parts():
        pending_dot = False

        for key, is_bearing in keys:
            if pending_dot:
                yield "."
                pending_dot = False

            yield key

            if is_bearing:
                yield ":"
            else:
                pending_dot = True

    return "".join(parts())


@dataclass(eq=False, frozen=True, slots=True, weakref_slot=True)
class Signature:
    """Relation signature: ordered keys, including non-bearing ones (for namespacing)"""

    keys: tuple[tuple[str, bool], ...]
    code: str
    bearing_keys: tuple[str] = field(init=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "bearing_keys",
            tuple(key for key, is_bearing in self.keys if is_bearing),
        )

    @property
    def dim(self):
        return len(self.bearing_keys)

    def __repr__(self):
        return f"#{self.code}"
