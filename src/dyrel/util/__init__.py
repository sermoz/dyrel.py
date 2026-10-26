from dataclasses import dataclass


def member_of(klass):
    def wrapper(member):
        assert not hasattr(klass, member.__name__), (
            f'Class {klass} already has member "{member.__name__}"'
        )
        setattr(klass, member.__name__, member)

    return wrapper

use_slots = dataclass(slots=True, eq=False, repr=False, init=False)
