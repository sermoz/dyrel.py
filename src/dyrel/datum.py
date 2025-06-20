from typing import Any

from dataclasses import dataclass, field
from cached_property import cached_property

from .util import NO_VALUE, get_attr_plain


class Relation_Root:
    def __getattribute__(self, name):
        if name.startswith("_"):
            return get_attr_plain(self, name)

        return Datum((Segment(name),))


class Datum:
    def __init__(self, chain):
        self._chain = chain

    def __getattribute__(self, name):
        if name.startswith("_"):
            return get_attr_plain(self, name)

        return Datum((*self._chain, Segment(name)))

    def __call__(self, arg):
        last_segment = self._chain[-1]

        if not last_segment.is_open:
            raise RuntimeError("Ill-formed datum (a call following another call)")

        return Datum((*self._chain[:-1], last_segment.value_set_to(arg)))

    def __repr__(self):
        return f"#<datum: {self._signature}>"

    @cached_property
    def _signature(self):
        pieces = []

        for segment in self._chain:
            if segment.is_open:
                pieces.append(f"{segment.name}.")
            else:
                pieces.append(f"{segment.name}:")

        return "".join(pieces)


@dataclass(slots=True, frozen=True)
class Segment:
    name: str
    value: Any = NO_VALUE

    @property
    def is_open(self):
        return self.value is NO_VALUE

    def value_set_to(self, value):
        return Segment(name=self.name, value=value)


R_OBJECT = Relation_Root()
