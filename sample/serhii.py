from dyrel import r

r += r.man("serhii")
r += r.man("vova")

r += r.person("vova").is_parent_of("serhii")

fuck = r.person("vova")

# pissa ---

r += fuck.is_parent_of("ira")
