from .dsl import RObject, VObject
from .loader import query

__all__ = ("query", "r", "v")


r = RObject()
v = VObject()
