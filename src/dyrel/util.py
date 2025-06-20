class Stub:
    __slots__ = "printed_name"

    def __init__(self, printed_name):
        self.printed_name = printed_name

    def __repr__(self):
        return f"#<{self.printed_name}>"


NO_VALUE = Stub("NO_VALUE")


get_attr_plain = object.__getattribute__
