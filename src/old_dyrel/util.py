import inspect
from collections.abc import Iterable

get_attr_plain = object.__getattribute__


def member_of(klass, override=False):
    def wrapper(member):
        assert override or not hasattr(klass, member.__name__), (
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


def initializer_for(slots):
    from inspect import Parameter, Signature

    sig = Signature([
        Parameter(slot, Parameter.POSITIONAL_OR_KEYWORD) for slot in slots
    ])

    def initializer(self, *args, **kwargs):
        arg_dict = sig.bind(*args, **kwargs).arguments

        for key, val in arg_dict.items():
            setattr(self, key, val)

    return initializer


def keyword_initializer_for(slots):
    from inspect import Parameter, Signature

    sig = Signature([
        Parameter(slot, Parameter.KEYWORD_ONLY) for slot in slots
    ])

    def initializer(self, **kwargs):
        arg_dict = sig.bind(**kwargs).arguments

        for key, val in arg_dict.items():
            setattr(self, key, val)

    return initializer
