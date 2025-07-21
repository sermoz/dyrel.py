from typing import TYPE_CHECKING

from dyrel.clause import Clause
from dyrel.datum import Datum, Open_Segment
from dyrel.projection import Projection
from dyrel.util import Slotted_Class

if TYPE_CHECKING:
    from dyrel.signature import Signature


relation_registry: dict["Signature", "Relation"] = {}


def get_relation(signature):
    try:
        relation = relation_registry[signature]
    except KeyError:
        relation = relation_registry[signature] = Relation(signature)

    return relation


class Relation(metaclass=Slotted_Class):
    signature: "Signature"
    clauses: list
    projections: dict

    def __init__(self, signature):
        self.signature = signature
        self.clauses = []
        self.projections = {}

    def add_clause(self, head_record, body):
        clause = Clause(head_record, body)

        self.clauses.append(clause)

        for proj in self.projections.values():
            proj.maybe_populate_by(clause)

    def get_projection(self, coords: tuple):
        try:
            proj = self.projections[coords]
        except KeyError:
            proj = self.projections[coords] = Projection(self, coords)

            for clause in self.clauses:
                proj.maybe_populate_by(clause)

        return proj
