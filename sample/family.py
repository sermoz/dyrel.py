from dyrel import or_, r, seq, v, agg, define_rule

r <<= (
    r.link.from_("Kyiv").to("Zhytomyr"),
    ...
)

r += r.path.from_(v.src).to(v.tgt).in_steps(1) <= r.link.from_(v.src).to(v.tgt)

r += r.path.from_(v.src).to(v.tgt).in_steps(v.n) <= (
    v.n_best == agg.min(v.n_intm, seq(
        r.path.from_(v.src).to(v.intm).in_steps(v.n_intm),
        r.link.from_(v.intm).to(v.tgt),
    )),
    v.n == v.n_best + 1,
)



r <<= (
    r.person("serhii").parent("vova"),
    r.person("serhii").parent("tanya"),
)

r <<= (
    r.person("serhii").man,
    r.person("vova").man,
)

r <<= r.person(v.P).father(-v.F) <= (
  r.person(v.P).parent(v.F),
  r.person(v.F).man,
)


r <<= r.person(v.P).father(+v.F) <= (
  r.person(v.F).man,
  r.person(v.P).parent(v.F),
)


define_rule(
    mode=mode(v, v) / mode(-v, -v),
    head=r.sale(v.sale).has_product(v.product).on_sale,
    body=(
        r.product_sale_settings(v.pss)(sale=0, product=0),
        r.sale(v.sale).point_of_sale(v.pos),
        branch(
            r.point_of_sale(v.pos).source(Source.transfer),
            r.product_sale_settings(v.pss).reissue_as_product(v != None),
            fail
        )
    )
)
