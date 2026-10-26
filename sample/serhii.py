from dyrel import r

r += r.man("serhii")
r += r.man("vova")

r += r.person("vova").is_parent_of("serhii")

# Comment!
fuck = r.person("vova")

r += fuck.is_parent_of("ira")
