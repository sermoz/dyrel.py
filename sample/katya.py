from __future__ import annotations

# r += r.woman("katya")
# r += r.woman("nadya")
# root("Our women", r.woman(v.W))
# # r += r.man("serhii")
# # Some comment!!
# r += (
# 	r.person("nadya").is_parent_of("katya")
# )
# @query(r.person(v.child).is_parent_of(v.child))
# def _vova_children(_added, child):
# 	print("Vova has a child:", child)
from dyrel import query, r, v


@query(r.man(v.Man))
def _all_men(added, Man):
    print(f'{"+" if added else "-"} man "{Man}"')


@query(r.man("serhii"))
def serhii_is_man(added):
    if added:
        print("Serhii is a man now!")
    else:
        print("Serhii is not a man anymore!")


@query(r.person(v.person).parent_of("serhii"))
def _serhii_parents(added, person):
    print(f'{"+" if added else "-"} parent of Serhii: "{person}"')


@query(r.person("tanya").parent_of(v.child))
def _tanya_children(added, child):
    print(f'{"+" if added else "-"} child of Tanya: "{child}"')


# @query(r.person(v.parent).parent_of(v.child))
# def _parent_chil(added, parent, child):
#     print(f'{"+" if added else "-"} "{parent}" -> "{child}"')
