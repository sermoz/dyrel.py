from collections.abc import Collection, Iterable
from weakref import WeakValueDictionary

from dyrel.util import Slotted_Class

signature_registry = WeakValueDictionary()


type Word = tuple[str, bool]


def get_signature(words: Collection[Word]):
    code = code_by_words(words)

    try:
        signature = signature_registry[code]
    except KeyError:
        signature = signature_registry[code] = Signature(list(words), code)

    return signature


def code_by_words(words: Iterable[Word]) -> str:
    def parts():
        pending_dot = False

        for name, is_bearing in words:
            if pending_dot:
                yield "."
                pending_dot = False

            yield name

            if is_bearing:
                yield ":"
            else:
                pending_dot = True

    return "".join(parts())


class Signature(metaclass=Slotted_Class):
    """Relation signature: ordered words, including non-bearing ones (for namespacing)"""

    words: list[Word]
    code: str
    bearing_words: list[str]

    def __init__(self, words, code):
        self.words = words
        self.code = code
        self.bearing_words = [key for key, is_bearing in words if is_bearing]

    @property
    def dim(self):
        return len(self.bearing_words)

    def __repr__(self):
        return f"#{self.code}"
