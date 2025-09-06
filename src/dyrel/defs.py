import enum

from dyrel.util import Stub

WILDCARD = Stub("*")


class Param_Dir(enum.IntFlag):
    In = 1
    Out = 2
    InOut = In | Out
