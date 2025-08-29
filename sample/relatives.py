from dyrel import r, v

r.person("serhii").parent("vova") <= ()
r.person("serhii").parent("tanya") <= ()

r.person("serhii").man <= ()
r.person("vova").man <= ()

r.person("tanya").woman <= ()

r.person("vova").is_friend_with(+v.friend) <= []

r.person(v.P).father(v.F) <= [
	r.person(v.P).parent(v.F),
	r.person(v.F).man,
	r.person(v.F).man,
]
