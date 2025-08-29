import enum
from collections.abc import Iterable
from typing import TYPE_CHECKING

from dyrel import util
from dyrel.phrase import Arg, Word, phrase_data

if TYPE_CHECKING:
    pass


relation_registry: dict[str, "Relation"] = {}


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
    apps: dict[bytes, "Relation_App_Mask"]

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


class Arg_Dir(enum.IntFlag):
    In = 1
    Out = 2
    InOut = In | Out


class Relation_App_Mask:
    dirs: list["Arg_Dir"]
    code: bytes

    __slots__ = util.annotated_vars()





def make_goal(phrase):
    words, args = phrase_data(phrase)
    relation = relation_by_words(words)
    return Goal(relation, args)


class Goal:
    relation: "Relation"
    args: list[Arg]

    __slots__ = util.annotated_vars()

    def __init__(self, relation, args):
        self.relation = relation
        self.args = args

