from typing import TYPE_CHECKING, Any, Optional, Union

from dyrel.signature import get_signature
from dyrel.util import Slotted_Class

if TYPE_CHECKING:
    from dyrel.signature import Signature


class Variable(metaclass=Slotted_Class):
    name: str

    is_ground = False


var_table = {}


class V_Object:
    def __getattr__(self, name):
        try:
            var = var_table[name]
        except KeyError:
            var = var_table[name] = Variable(name)

        return var


# v_object = V_Object()


class Relation_Root:
    def __getattr__(self, name):
        return Word_Chain(None, name)


# r_object = Relation_Root()


class Atom(metaclass=Slotted_Class):
    """A value that goes with a closed segments in a phrase"""
    val: Any

    is_ground = True


type Argument = Variable | Atom


def phrase_argument(arg) -> Argument:
    return arg if isinstance(arg, Variable) else Atom(arg)


class Word_Chain(metaclass=Slotted_Class):
    """A phrase represented as a reversed list of words and their arguments."""

    _prev: Optional["Word_Chain"]
    _name: str
    _arg: Optional["Argument"]

    def __init__(self, prev, name, arg=None):
        self._prev = prev
        self._name = name
        self._arg = arg

    def __getattr__(self, name):
        return Word_Chain(self, name)

    def __call__(self, value):
        if self._arg is None:
            return Word_Chain(self._prev, self._name, phrase_argument(value))
        else:
            raise RuntimeError("Ill-formed phrase (a call following another call)")

    def __repr__(self):
        # TODO: implement
        return f"<Phrase: {0}>"


# def is_phrase_open(phrase):
#     return phrase._atom is None


# def word_chain_signature(chain):
#     words = []

#     while chain is not None:
#         words.append((chain._name, chain._arg is not None))
#         chain = chain._prev

#     words.reverse()

#     return get_signature(words)


def phrase_by_word_chain(chain):
    words, args = [], []

    while chain is not None:
        words.append((chain._name, chain._arg is not None))

        if chain._arg is not None:
            args.append(chain._arg)

        chain = chain._prev

    words = tuple(reversed(words))
    args = tuple(reversed(args))

    return Phrase(signature=get_signature(words), args=args)


class Phrase(metaclass=Slotted_Class):
    signature: "Signature"
    args: tuple[Argument]
