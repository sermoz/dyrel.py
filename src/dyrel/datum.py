from typing import TYPE_CHECKING, Any, Optional, Union

from dyrel.signature import get_signature
from dyrel.util import Slotted_Class, init_with_kwargs

if TYPE_CHECKING:
    from dyrel.signature import Signature


Segment = Union["Closed_Segment", "Open_Segment"]


class Datum(metaclass=Slotted_Class):
    _segments: tuple["Segment", ...]
    _sig: Optional["Signature"]

    def __init__(self, segment_chain: tuple):
        self._segments = segment_chain
        self._sig = None

    def __getattr__(self, name):
        return Datum((*self._segments, Open_Segment(name)))

    def __call__(self, value):
        return Datum((*self._segments[:-1], self._segments[-1].as_bearing(value)))

    def __repr__(self):
        return f"<datum: {self._signature}>"

    @property
    def _signature(self) -> "Signature":
        if self._sig is None:
            self._sig = get_signature(
                (seg.name, seg.is_bearing) for seg in self._segments
            )

        return self._sig


class Closed_Segment(metaclass=Slotted_Class):
    """A segment that bears the real value in it.

    Example:
        r.person("John").workwise.happy_points(6)
        r.person("John").familywise.happy_points(9)

    The .person("John"), .happy_points(6) are bearing segments.
    """
    name: str
    value: Any

    is_bearing = True

    __init__ = init_with_kwargs

    def as_bearing(self, value):
        raise RuntimeError("Ill-formed datum (a call following another call)")


class Open_Segment(metaclass=Slotted_Class):
    """A segment that's used only for namespacing, i.e. not bearing a value.

    Example:
        r.person("John").workwise.happy_points(6)
        r.person("John").familywise.happy_points(9)

    The .workwise, .familywise above are namespacing segments.
    """

    name: str

    is_bearing = False

    def __init__(self, name):
        self.name = name

    def as_bearing(self, value):
        return Closed_Segment(name=self.name, value=value)
