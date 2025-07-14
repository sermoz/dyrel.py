from typing import TYPE_CHECKING

from dyrel.datum import Datum, Open_Segment
from dyrel.projection import Projection

if TYPE_CHECKING:
    from dyrel.signature import Signature


class Relation_Root:
    def __getattr__(self, name):
        return Datum((Open_Segment(name),))


r_object = Relation_Root()

relation_registry: dict["Signature", "Relation"] = {}


def get_relation(signature):
    try:
        relation = relation_registry[signature]
    except KeyError:
        relation = relation_registry[signature] = Relation(signature)

    return relation


class Relation:
    def __init__(self, signature):
        self.signature = signature
        self.facts = set()  # clauses without bodies
        self.projections = {}

    def add_fact(self, record):
        self.facts.add(record)

        for proj in self.projections.values():
            proj.consider_adding(record)

    def get_projection(self, coords: tuple):
        try:
            proj = self.projections[coords]
        except KeyError:
            proj = self.projections[coords] = Projection(self, coords)

            for fact in self.facts:
                proj.consider_adding(fact)

        return proj
