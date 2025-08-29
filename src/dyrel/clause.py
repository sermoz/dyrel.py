from typing import TYPE_CHECKING, Optional

from dyrel.defs import WILDCARD
from dyrel.util import Slotted_Class
from dyrel.variable import Variable
from dyrel.phrase import phrase_words

if TYPE_CHECKING:
    from dyrel.phrase import Arg, Phrase
    from dyrel.relation import Relation


class Clause:
    relation: "Relation"
    head_args: list["Arg"]
    body: list["Goal"]

    def __init__(self, head_record, body):
        self.head_record = head_record
        self.body = body


def declare_clause(head_phrase, body_phrases):
    words = phrase_words(head_phrase)
    relation = relation_by_words(words)
    body_goals = [make_goal(phrase) for phrase in body_phrases]
