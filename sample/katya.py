from dyrel import r

r += r.woman("katya")
r += r.woman("nadya")

# Some comment!
r += (
	r.person("nadya").is_parent_of("katya")
)
