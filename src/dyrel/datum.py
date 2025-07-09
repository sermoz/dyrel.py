from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from dyrel.signature import get_signature
from dyrel.util import NO_VALUE, Slotted_Class

if TYPE_CHECKING:
    from dyrel.signature import Signature


class Datum(metaclass=Slotted_Class):
    _chain: tuple["Segment", ...]
    _sig: Optional["Signature"]

    def __init__(self, chain):
        self._chain = chain
        self._sig = None

    def __getattr__(self, name):
        return Datum((*self._chain, Segment(name)))

    def __call__(self, arg):
        last_segment = self._chain[-1]

        if last_segment.is_bearing:
            raise RuntimeError("Ill-formed datum (a call following another call)")

        return Datum((*self._chain[:-1], last_segment.but_value(arg)))

    def __repr__(self):
        return f"<datum: {self._signature}>"

    def _as_record(self):
        return tuple(seg.value for seg in self._chain if seg.is_bearing)

    @property
    def _signature(self) -> "Signature":
        if self._sig is None:
            self._sig = get_signature((seg.name, seg.is_bearing) for seg in self._chain)

        return self._sig


@dataclass(frozen=True, slots=True)
class Segment:
    name: str
    value: Any = NO_VALUE

    @property
    def is_bearing(self):
        return self.value is not NO_VALUE

    def but_value(self, value):
        return Segment(name=self.name, value=value)
