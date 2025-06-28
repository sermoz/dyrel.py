from dataclasses import dataclass
from typing import Any

from dyrel.util import NO_VALUE


class Datum:
    def __init__(self, chain):
        self._chain = chain

    def __getattr__(self, name):
        return Datum((*self._chain, Segment(name)))

    def __call__(self, arg):
        last_segment = self._chain[-1]

        if last_segment.is_bearing:
            raise RuntimeError("Ill-formed datum (a call following another call)")

        return Datum((*self._chain[:-1], last_segment.but_value(arg)))

    def __repr__(self):
        return f"<datum: {self._signature}>"


@dataclass(frozen=True, slots=True)
class Segment:
    name: str
    value: Any = NO_VALUE

    @property
    def is_bearing(self):
        return self.value is not NO_VALUE

    def but_value(self, value):
        return Segment(name=self.name, value=value)
