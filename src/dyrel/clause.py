from typing import TYPE_CHECKING, Optional

from dyrel.defs import WILDCARD
from dyrel.util import Slotted_Class
from dyrel.variable import Variable

if TYPE_CHECKING:
    from dyrel.phrase import Phrase
    from dyrel.relation import Relation


class Clause(metaclass=Slotted_Class):
    # relation: "Relation"
    head_record: tuple
    body: tuple["Phrase", ...]
    num_vars: int
    spec_map: dict

    def __init__(self, head_record, body):
        self.head_record = head_record
        self.body = body
        self.num_vars = sum(1 for x in self.head_record if isinstance(x, Variable))
        self.spec_map = {}

    def consider_filling(self, proj) -> bool:
        assert len(self.head_record) == len(proj.coords)

        generalizations = []
        spec = []

        for C, P in zip(self.head_record, proj.coords):
            if isinstance(C, Variable):
                spec.append(None if P is WILDCARD else P)
            elif P is WILDCARD:
                generalizations.append(True)
            elif C == P:
                generalizations.append(False)
            else:
                return False  # this clause does not agree with the projection

        spec = tuple(spec)

        try:
            instantiation = self.spec_map[spec]
        except KeyError:
            instantiation = self.spec_map[spec] = Clause_Instantiation(self, spec)

        generalization_code = bytes(int(g) for g in generalizations)

        instantiation.add_projection(generalization_code, proj)

        return True  # successfully matched


class Clause_Config(metaclass=Slotted_Class):
    """Join configuration of a clause: at which goal which variables are in/out."""

    clause: "Clause"
    spec_mask: bytes
    goal_configs: list["Goal_Config"]


class Goal_Config(metaclass=Slotted_Class):
    clause_config: "Clause_Config"
    depth: int



class Clause_Instantiation(metaclass=Slotted_Class):
    clause: "Clause"
    spec: tuple
    gen_map: dict

    def __init__(self, clause, spec):
        self.clause = clause
        self.spec = spec
        self.gen_map = {}

    def add_projection(self, gen_code: bytes, proj):
        self.gen_map[gen_code] = proj


class Join_Node(metaclass=Slotted_Class):
    parent: Optional["Join_Node"]
    depth: int
    proj: "Projection"
    snapshot: Optional["Snapshot"]
    children: set | dict  # at the last level use set, otherwise dict of record -> node

    def __init__(self, parent):
        self.parent = parent
        self.depth = self.parent.depth + 1
        self.bound_vars = {}

    def on_record_added(self, record):
        pass

    def on_record_removed(self, record):
        pass
