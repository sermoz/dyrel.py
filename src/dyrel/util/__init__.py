from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


def group_by(items: Iterable, key: Callable) -> dict:
    result = {}

    for item in items:
        result.setdefault(key(item), []).append(item)

    return result


class SetMembership:
    def __init__(self, true_set: set):
        self.true_set = true_set

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        return instance in self.true_set

    def __set__(self, instance, value: bool):
        if value:
            self.true_set.add(instance)
        else:
            self.true_set.discard(instance)


class ExternalAttr:
    def __init__(self, table: dict):
        self.table = table

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        return instance in self.true_set

    def __set__(self, instance, value: bool):
        if value:
            self.true_set.add(instance)
        else:
            self.true_set.discard(instance)
