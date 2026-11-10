from dyrel import r

r += r.man("serhii")
r += r.man("yura")
r += r.man("vova")
r += r.man("nicik")
r += r.man("kolya")

# r += r.person("vova").parent_of("serhii")
r += r.person("tanya").parent_of("serhii")
r += r.person("tanya").parent_of("ira")
r += r.person("tanya").parent_of("ryba")
# r += r.person("yura")
