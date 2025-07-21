import inspect
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from dyrel.util import Slotted_Class


class Stub(metaclass=Slotted_Class):
    printed_name: str

    def __repr__(self):
        return f"<stub: {self.printed_name}>"


NO_VALUE = Stub("NO_VALUE")


get_attr_plain = object.__getattribute__


def member_of(klass):
    def wrapper(member):
        assert not hasattr(klass, member.__name__), (
            f'Class {klass} already has member "{member.__name__}"'
        )
        setattr(klass, member.__name__, member)
        return None

    return wrapper


class cached_property:
    """A property that is only computed once per instance and then replaces itself with an ordinary attribute.

    Deleting the attribute resets the property.
    This is modelled after the standard pypi "cached_property" package but also has some needed modifications.
    """  # noqa

    def __init__(self, func):
        self.__doc__ = getattr(func, "__doc__")

        if hasattr(func, "__name__"):
            self.__name__ = func.__name__

        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


class Slotted_Class(type):
    def __new__(cls, name, bases, namespace):
        if "__annotations__" not in namespace:
            return super().__new__(cls, name, bases, namespace)

        if "__slots__" in namespace:
            raise RuntimeError(f"{name}: '__slots__' is not expected")

        annotations = namespace["__annotations__"]
        namespace["__slots__"] = tuple(annotations.keys())

        if "__init__" not in namespace:
            namespace["__init__"] = slotted_class_initializer(namespace["__slots__"])

        return super().__new__(cls, name, bases, namespace)


def to_tuple(thing: Iterable) -> tuple:
    return thing if isinstance(thing, tuple) else tuple(thing)


def slotted_class_initializer(slots):
    sig = inspect.Signature([
        inspect.Parameter(slot, inspect.Parameter.POSITIONAL_OR_KEYWORD) for slot in slots
    ])

    def initializer(self, *args, **kwargs):
        arg_dict = sig.bind(*args, **kwargs).arguments

        for key, val in arg_dict.items():
            setattr(self, key, val)

    return initializer
