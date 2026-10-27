from dyrel import r

r += r.man("serhii")
r += r.man("vova")

r += r.person("vova").is_parent_of("serhii")

# Comment!
r += r.person("vova").is_parent_of("ira")
r += r.person("tanya").is_parent_of("ira")
