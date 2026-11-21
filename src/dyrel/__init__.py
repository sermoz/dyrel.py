from .dsl import RObject, VObject
from .host.load import query

__all__ = ("query", "r", "v")


r = RObject()
v = VObject()
