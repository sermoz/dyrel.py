from typing import TYPE_CHECKING

from dyrel.relation import get_relation

if TYPE_CHECKING:
    pass


class Node:
    pass


def add_clause(head, body=None):
    relation = get_relation(head._signature)
    relation.add_clause(head, body)


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
