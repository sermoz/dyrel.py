from dyrel import r

r += r.woman("katya")
r += r.woman("nadya")

r += r.person("nadya").is_parent_of("katya")
