from typing import TYPE_CHECKING

from dyrel.relation import get_relation

if TYPE_CHECKING:
    from dyrel.datum import Datum


class Node:
    pass


def declare(fact: "Datum"):
    if not fact._is_ground:
        raise RuntimeError("Can only declare facts!")

    relation = get_relation(fact._signature)
    relation.add_fact(fact._as_record())


def query(datum):
    relation = get_relation(datum._signature)
    proj = relation.get_projection(datum._as_projection_coords())
    key_names = datum._variable_names()

    def decorator(callback):
        proj.add_observer(
            on_add=lambda record: callback(**dict(zip(key_names, record))),
            on_remove=lambda record: print("Record deleted: ", record),
        )
        return None

    return decorator
