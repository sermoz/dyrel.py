class Clause_Instantiation(metaclass=Slotted_Class):
#     clause: "Clause"
#     spec: tuple
#     gen_map: dict

#     def __init__(self, clause, spec):
#         self.clause = clause
#         self.spec = spec
#         self.gen_map = {}

#     def add_projection(self, gen_code: bytes, proj):
#         self.gen_map[gen_code] = proj


# type Var_Coords = tuple[int, int]


# class Var_Registry(metaclass=Slotted_Class):
#     var_coords: dict
#     depth: int
#     vnum: int

#     def __init__(self):
#         self.var_coords = {}
#         self.depth = 0
#         self.vnum = 0

#     def met_var(self, name) -> tuple[Var_Coords, bool]:
#         if name in self.var_coords:
#             return self.var_coords[name], False

#         self.var_coords[name] = (self.depth, self.vnum)
#         self.vnum += 1

#         return self.var_coords[name], True

#     def shift_to_next_goal(self):
#         self.depth += 1
#         self.vnum = 0


# def build_clause_config(clause, spec_mask):
#     var_reg = Var_Registry()

#     head_vars = [var.name for var in clause.head.args if isinstance(var, Variable)]

#     for var, is_spec in zip(head_vars, spec_mask):
#         if is_spec:
#             var_reg.met_var(var)

#     for goal in clause.body:
#         var_reg.shift_to_next_goal()

#         proj_coords_template = []
#         num_out_vars = 0

#         for arg in goal.args:
#             if isinstance(arg, Variable):
#                 coords, free = var_reg.met_var(arg.name)

#                 if free:
#                     num_out_vars += 1
#                     proj_coords_template.append(WILDCARD)
#                 else:
#                     proj_coords_template.append(var_reg.reference_to(coords))
#             else:
#                 pass


# def var_ref(var_coords):
#     pass


# class Clause_Config(metaclass=Slotted_Class):
#     """Join configuration of a clause: at which goal which variables are in/out."""

#     clause: "Clause"
#     spec_mask: bytes
#     goal_configs: list["Goal_Config"]


# class Goal_Config(metaclass=Slotted_Class):
#     clause_config: "Clause_Config"
#     depth: int





# class Join_Node(metaclass=Slotted_Class):
#     proj: "Projection"
#     snapshot: "Snapshot"
#     parent_rec: tuple
#     parent: Optional["Join_Node"]
#     children: set | dict  # at the last level use set, otherwise dict of record -> node
#     depth: int

#     def __init__(self, parent):
#         self.parent = parent
#         self.depth = self.parent.depth + 1
#         self.bound_vars = {}

#     def on_record_added(self, record):
#         pass

#     def on_record_removed(self, record):
#         pass
