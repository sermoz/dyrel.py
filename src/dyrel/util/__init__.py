from typing import Iterable, Callable
from dataclasses import dataclass


def member_of(klass):
    def wrapper(member):
        assert not hasattr(klass, member.__name__), (
            f'Class {klass} already has member "{member.__name__}"'
        )
        setattr(klass, member.__name__, member)

    return wrapper


def group_by(items: Iterable, key: Callable) -> dict:
    result = {}

    for item in items:
        result.setdefault(key(item), []).append(item)

    return result


use_slots = dataclass(slots=True, eq=False, repr=False, init=False)
