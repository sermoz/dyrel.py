from typing import TYPE_CHECKING, Any, Optional

from dyrel import util

if TYPE_CHECKING:
    pass
    # from dyrel.signature import Signature


class V_Object:
    def __getattr__(self, name):
        return Var(name)


class Var:
    name: str

    __slots__ = util.annotated_vars()

    is_var = True

    def __init__(self, name):
        self.name = name

    def __eq__(self, other_var):
        return isinstance(other_var, Var) and self.name == other_var.name


class Val:
    val: Any

    __slots__ = util.annotated_vars()

    is_var = False

    def __init__(self, val):
        self.val = val


type Arg = Var | Val


def make_arg(thing) -> Arg:
    return thing if isinstance(thing, Var) else Val(thing)


class Relation_Root:
    def __getattr__(self, name):
        return Phrase(None, name)


class Phrase:
    """A phrase is represented as a reverse list of words and their arguments"""

    _prev: Optional["Phrase"]
    _name: str
    _arg: Arg | None

    __slots__ = util.annotated_vars()

    def __init__(self, prev, name, arg=None):
        self._prev = prev
        self._name = name
        self._arg = arg

    def __getattr__(self, name):
        return Phrase(self, name)

    def __call__(self, value):
        if self._arg is None:
            return Phrase(self._prev, self._name, make_arg(value))
        else:
            raise RuntimeError("Ill-formed phrase (a call following another call)")

    def __le__(self, body_phrases):
        from dyrel.relation import declare_clause

        declare_clause(self, body_phrases)

    def __repr__(self):
        # TODO: implement
        return f"<Phrase: {0}>"


# True if there's argument, False if it's just for namespacing.
type Word = tuple[str, Arg | None]


def phrase_words(phrase) -> list[Word]:
    words = []

    while phrase is not None:
        words.append((phrase._name, phrase._arg))
        phrase = phrase._prev

    words.reverse()

    return words
