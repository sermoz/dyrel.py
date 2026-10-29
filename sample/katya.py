from dyrel import r, root, v

r += r.woman("katya")
r += r.woman("nadya")

root("Our women", r.woman(v.W))


# r += r.man("serhii")

# Some comment!!
r += (
	r.person("nadya").is_parent_of("katya")
)


root("Vova's children", r.person("vova").is_parent_of(v.Child))
