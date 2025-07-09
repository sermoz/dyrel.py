from dataclasses import dataclass

from dyrel.datum import Datum
from dyrel.util import member_of

var_table = {}


class V_Object:
    def __getattr__(self, name):
        if name not in var_table:
            var_table[name] = Variable(name)

        return var_table[name]


v_object = V_Object()


@dataclass(eq=False, frozen=True, slots=True)
class Variable:
    name: str


@member_of(Datum)
def _is_ground(self):
    """Does the datum not contain any variables?"""
    return not any(isinstance(seg.value, Variable) for seg in self._chain)
