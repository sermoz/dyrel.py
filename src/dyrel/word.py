from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from dyrel import util
from dyrel.defs import Param_Dir

if TYPE_CHECKING:
    pass


class V_Object:
    def __getattr__(self, name):
        parent_frame = inspect.currentframe().f_back
        return Var(name, parent_frame.f_lineno)


class Var:
    name: str
    lineno: int | None
    dir: Param_Dir | None

    __slots__ = util.annotated_vars()

    is_var = True

    def __init__(self, name, lineno=None, dir=None):
        self.name = name
        self.lineno = lineno
        self.dir = dir

    def __eq__(self, var):
        return isinstance(var, Var) and self.name == var.name

    def __pos__(self):
        if self.dir is not None:
            raise RuntimeError(f"Double dir spec applied to a variable '{self.name}'")

        return Var(self.name, self.lineno, Param_Dir.In)

    def __neg__(self):
        if self.dir is not None:
            raise RuntimeError(f"Double dir spec applied to a variable '{self.name}'")

        return Var(self.name, self.lineno, Param_Dir.Out)


class Val:
    val: Any

    __slots__ = util.annotated_vars()

    is_var = False

    def __init__(self, val):
        self.val = val


type Arg = Var | Val


def make_arg(thing) -> Arg:
    return thing if isinstance(thing, Var) else Val(thing)


class Word_Chain_Start:
    lineno: int

    __slots__ = util.annotated_vars()

    is_start = True

    def __init__(self, lineno):
        self.lineno = lineno


class Word_Chain:
    """Words form up a singly-linked list with the last one being the head"""

    _prev: Word_Chain | Word_Chain_Start
    _word: str
    _arg: Arg | None

    __slots__ = util.annotated_vars()

    is_start = False

    def __init__(self, prev, name, arg=None):
        self._prev = prev
        self._word = name
        self._arg = arg

    def __getattr__(self, name):
        return Word_Chain(self, name)

    def __call__(self, value):
        if self._arg is not None:
            raise RuntimeError("Ill-formed relation application (a call following another call)")

        return Word_Chain(self._prev, self._word, make_arg(value))

    # def __repr__(self):
    #     # TODO: implement
    #     return f"<Phrase: {0}>"
