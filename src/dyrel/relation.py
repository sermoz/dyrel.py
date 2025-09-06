from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from dyrel import util
from dyrel.word import Arg, Word_Chain, Word_Chain_Start

if TYPE_CHECKING:
    from collections.abc import Iterable


class Relation_Root:
    def __getattr__(self, name):
        parent_frame = inspect.currentframe().f_back
        return Word_Chain(Word_Chain_Start(parent_frame.f_lineno), name)


# TODO: continue here. We should just accumulate all the collected clauses in a file's
# data structure, then process them after the file is done executing.
CLAUSES = []


@util.member_of(Word_Chain, override=True)
def __le__(self, body):
    """The less-equal (<=) operator to declare clauses, typically at module level.

    Example:
        R.person(v.P).child_of(v.F) <= (
           R.person(v.F).parent_of(v.P),
           ....
        )
    """
    CLAUSES.append((self, body))
    return True

    if not all(isinstance(goal, Word_Chain) for goal in body):
        raise RuntimeError("Bad clause body")

    head_lineno, head_args = reverse_word_chain(self)


    return True  # does not matter


type Word_Arg = tuple[str, Arg | None]


def reverse_word_chain(chain: Word_Chain) -> tuple[int, list[Word_Arg]]:
    pairs = []

    while not chain.is_start:
        pairs.append((chain._word, chain._arg))
        chain = chain._prev

    pairs.reverse()

    return chain.lineno, pairs


def make_rel_app_by_word_chain(chain: Word_Chain) -> Relation_Application:
    lineno, word_args = reverse_word_chain(chain)

    for _word, arg in word_args:
        if arg is not None and arg.is_var and arg.dir is not None:
            raise RuntimeError("Variable in a goal is decorated with a dir spec")

    return Relation_Application()


class Relation_Application:
    relation: Relation
    args: list[Arg]
    lineno: int

    __slots__ = util.annotated_vars()
    __init__ = util.keyword_initializer



relation_registry: dict[str, Relation] = {}


def relation_by_words(words: list[Word]):
    code = code_by_words(words)

    try:
        relation = relation_registry[code]
    except KeyError:
        relation = relation_registry[code] = Relation(words, code)

    return relation


def code_by_words(words: Iterable[Word]) -> str:
    """Get relation code (a string) by the iterable of words"""
    def parts():
        pending_dot = False

        for name, is_bearing in words:
            if pending_dot:
                yield "."
                pending_dot = False

            yield name

            if is_bearing:
                yield ":"
            else:
                pending_dot = True

    return "".join(parts())


type Word_Loaded = tuple[str, bool]


class Relation:
    words: list[Word_Loaded]
    arity: int
    code: str
    clauses: list
    apps: dict[bytes, Rel_App_Flow]

    __slots__ = util.annotated_vars()

    def __init__(self, words, code):
        self.words = words
        self.arity = sum(1 for _word, is_loaded in words if is_loaded)
        self.code = code
        self.clauses = []

    # def add_clause(self, head_record, body):
    #     clause = Clause(head_record, body)

    #     self.clauses.append(clause)

    #     for proj in self.projections.values():
    #         proj.maybe_populate_by(clause)

    # def get_projection(self, coords: tuple):
    #     try:
    #         proj = self.projections[coords]
    #     except KeyError:
    #         proj = self.projections[coords] = Projection(self, coords)

    #         for clause in self.clauses:
    #             proj.maybe_populate_by(clause)

    #     return proj




class Rel_App_Flow:
    dirs: list[Param_Dir]
    mask: bytes

    __slots__ = util.annotated_vars()


# def make_goal(phrase):
#     words, args = phrase_data(phrase)
#     relation = relation_by_words(words)
#     return Goal(relation, args)


# class Goal:
#     relation: "Relation"
#     args: list[Arg]

#     __slots__ = util.annotated_vars()

#     def __init__(self, relation, args):
#         self.relation = relation
#         self.args = args

