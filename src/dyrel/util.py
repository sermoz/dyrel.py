from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(eq=False, slots=True)
class Stub:
    printed_name: str

    def __repr__(self):
        return f"<stub: {self.printed_name}>"


NO_VALUE = Stub("NO_VALUE")


get_attr_plain = object.__getattribute__


# def method_for(*klasses):
#     def install_in(fn, klass):
#         name = fn.__name__
#         assert not hasattr(klass, name), f"Class {klass} already has member \"{name}\""
#         setattr(klass, name, fn)

#     def wrapper(fn):
#         for klass in klasses:
#             install_in(fn, klass)

#         return None  # don't put real fn in whatever namespace this decorator is being used in

#     return wrapper


# def property_for(*klasses):
#     def install_in(fn, klass):
#         name = fn.__name__
#         assert not hasattr(klass, name), f"Class {klass} already has member \"{name}\""
#         setattr(klass, name, property(fn))

#     def wrapper(fn):
#         for klass in klasses:
#             install_in(fn, klass)

#         return None  # don't put real fn in whatever namespace this decorator is being used in

#     return wrapper


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
            raise RuntimeError("__slots__ is already present, it is not expected")

        annotations = namespace["__annotations__"]
        namespace["__slots__"] = tuple(annotations.keys())

        return super().__new__(cls, name, bases, namespace)


def tuplify(thing: Iterable) -> tuple:
    return thing if isinstance(thing, tuple) else tuple(thing)


def init_with_kwargs(self, **kwargs):
    for key, val in kwargs.items():
        setattr(self, key, val)
