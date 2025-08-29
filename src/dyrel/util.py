import inspect
from collections.abc import Iterable

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


def to_tuple(thing: Iterable) -> tuple:
    return thing if isinstance(thing, tuple) else tuple(thing)


def annotated_vars():
    """Extracts all the annotated variables of the calling frame"""
    return list(inspect.currentframe().f_back.f_locals["__annotations__"])


def keyword_initializer(self, **kwargs):
    for key, val in kwargs.items():
        setattr(self, key, val)
