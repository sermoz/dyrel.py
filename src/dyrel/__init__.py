from .dsl import RObject, VObject
from .load import query

__all__ = ("query", "r", "v")


r = RObject()
v = VObject()
