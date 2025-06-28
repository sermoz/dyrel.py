from typing import TYPE_CHECKING

from dyrel.datum import Datum, Segment

if TYPE_CHECKING:
    from dyrel.signature import Signature


class Relation_Root:
    def __getattr__(self, name):
        return Datum((Segment(name),))


r_object = Relation_Root()

relation_registry: dict["Signature", "Relation"] = {}


class Relation:
    def __init__(self, signature):
        self.signature = signature
        self.facts = []
        self.projections = []

    def add_fact(self, fact: Datum):
        self.facts.append(fact)


def declare(fact):
    if not fact._is_ground:
        raise RuntimeError("Can only declare facts!")

    try:
        relation = relation_registry[fact._signature]
    except KeyError:
        relation = relation_registry[fact._signature] = Relation(fact._signature)

    relation.add_fact(fact)
