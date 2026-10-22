from dataclasses import dataclass

from dyrel.datum import Datum
from dyrel.util import Slotted_Class, member_of



@member_of(Datum)
def _is_ground(self):
    """Does the datum not contain any variables?"""
    return not any(isinstance(value, Variable) for value in self._values())
