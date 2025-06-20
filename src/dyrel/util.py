from dataclasses import dataclass

@dataclass(slots=True, eq=False, repr=False)
class Stub:
    printed_name: str

    def __repr__(self):
        return f"#<{self.printed_name}>"


NO_VALUE = Stub("NO_VALUE")


get_attr_plain = object.__getattribute__
