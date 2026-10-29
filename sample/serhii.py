from dyrel import r, v, root

root("Is Serhii a man?", r.man("serhii"))

# r += r.man("serhii")
r += r.man("yura")
r += r.man("vova")

r += r.person("vova").is_parent_of("serhii")
# r += r.person("vova").is_parent_of("unborn")

# fuck()

# fucking sheet

# Comment!
r += r.person("vova").is_parent_of("ira")
r += r.person("tanya").is_parent_of("ira")
# r += r.person("tanya").is_parent_of("serhii")

# r += r.something.totally.different(10)
# r += r.something.totally.other(0)

# r += r.woman("polya")
# r += r.woman("polya")


root("Serhii's parents", r.person(v.Parent).is_parent_of("serhii"))
