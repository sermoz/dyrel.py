from dyrel import R, v

R.person("serhii").father(v.father) <= (
    R.person(v.person_A).father(v.person_B),
    R.artist(v.person_B).teacher(v.dad),
)

# r.person("serhii").parent("vova") <= ()
# r.person("serhii").parent("tanya") <= ()

# r.person("serhii").man <= ()
# r.person("vova").man <= ()

# r.person("tanya").woman <= ()

# # r.person("vova").is_friend_with(+v.__) <= ()

# r.person(v.P).father(v.F) <= [
#   r.person(v.P).parent(v.F),
#   r.person(v.F).man,
#   r.person(v.F).man,
# ]
