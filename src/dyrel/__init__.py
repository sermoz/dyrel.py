__version__ = "0.1.0"

#from dyrel.word import V_Object
#from dyrel.relation import Relation_Root

# r = Relation_Root()
# v = V_Object()


def concat(items, convertor=str):
	return "".join([convertor(item) for item in items])


__all__ = ("r", "v")


