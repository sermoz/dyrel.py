# DyRel design summary (session notes)

Purpose of this file: record the design decisions reached in the "Dyrel
design" discussion sessions, in enough detail that a fresh session (human or
assistant) can pick up the context without re-deriving it. It is not the
document to present to the team; that one is still to be written.

Where this file conflicts with `docs/readme.full.md`, this file wins. A
mapping from older vocabulary is at the end.

Status markers: "settled" means agreed in discussion; "later" means agreed
to be out of v0; "open" means explicitly undecided.

---

## 1. What DyRel is

A Python-embedded, Datalog-based relational engine with incremental
evaluation, reactivity, SQL/ORM integration and live interactive development
(autoreload). Relations are defined by rules written in Python syntax against
a `r` object (relations) and a `v` object (variables). Evaluation is
top-down and demand-driven; results are materialized in *slices* and kept
up to date lazily as leaf data changes.

---

## 2. Terminology (settled)

- **relation**: a named set of records. Use "relation" over "predicate".
- **signature / relation signature**: the name of a relation, a chain of
  *segments* such as `order.subtotal` or `rate.from_.to_`. Segment
  chains are a way of combining keywords into one name; they are *not*
  hierarchical and imply no relationship between `order.subtotal` and
  `order.uid`. Never "path".
- **segment / signature segment**: one element of a signature. Bare
  (`.subtotal`) or carrying one argument (`.city(v.C)`).
- **position**: an argument slot of a relation. A segment with an argument
  contributes one position. A trailing `== X` fills the argument of the
  bare trailing segment (§3). Each position is a key position or the
  relation's single FD position.
- **goal / subgoal / relation application**: a use of a relation inside a
  rule. The head is the goal; the body conjuncts are subgoals, the things
  that must be satisfied to satisfy the head. "Relation application" and
  "subgoal" are interchangeable; each body subgoal becomes one plan step.
- **mode**: which positions of a relation application are bound (`+`) or
  free (`-`) at planning time. Written like `+O -C`. Never "adornment".
- **slice**: the materialized records of one relation in one mode for one
  tuple of bound key values, together with its completeness certificate,
  version chain and `subscribers`. Corresponds to a *tabled subgoal* in
  XSB-style tabling. Never "projection" (that word means column selection
  in relational algebra).
- **record**: an element of a slice: the tuple of free-position values
  (plus the FD value, if any). Records have no identity beyond their
  value; set semantics with an internal support count (§8). Never "row".
- **solution**: one distinct binding of *all* body variables of a rule,
  before projection. Many solutions may map to one record (§8). Not a
  synonym of record.
- **tuple**: a plain Python tuple used as a key.
- **value struct**: an immutable, hashable Python compound value (tuple,
  named tuple, frozen dataclass, frozenset) used as a value or a key;
  identified by its contents (§3). Never "object" or "entity", which are
  reserved for the deferred identity story (§14).
- **multi-value head** (informally *hydra*): a head with keyword items,
  defining several relations from one body evaluation (§5).
- **env**: the live variables of a rule instance at a point of the
  plan. Conceptual; at runtime it is the positional `args` tuple of a
  node (§8), never a dict except when reconstructed for debugging.
- **node / derivation node / join node**: the per-generator-item object
  created during evaluation; the unit of retraction and the only
  evaluation object with identity (§8). "Plan step" is the static thing
  in a plan; a node is its instance for one env. Never "record" (that
  word now means a slice element).
- **subscription / dependency edge**: a node (join node) in
  `slice.subscribers`, holding the version of the slice it last
  observed. Slice level only; there is no per-record index on the producer
  side (§8).
- **leaf**: a relation whose records come from outside the rule system: an
  ORM-mapped table, or another fact source. Leaves are implemented
  specially by the engine (§7).
- **facade**: the Python-side object for interactive/imperative access to
  relations by fixed key (§11). A naming convention lives only there.

---

## 3. Relation shape (settled)

A relation is designated by a signature whose segments are each bare or
carry exactly one argument. Every argument is a **key position**, with
one exception: when the signature ends in a bare segment and is written
`sig == X`, X becomes that segment's argument and is the relation's
single **FD position**, functionally determined by all key positions.
Informally the FD position is the relation's *value*; "value" is short
for "the position with the FD contract".

Consequences:

- A relation has zero or more key positions and at most one FD position,
  always the last position and always named by its segment. Zero-key
  relations exist (constants); whether zero-key relations with an FD
  position are needed is open.
- A record is the key tuple plus the value, if any.
- No relation has several FD positions. Several values sharing a key are
  either several relations, defined together by a multi-value head (§5)
  and read together by the combined form (§4), or one value struct
  (below) in one FD position. This is a reactivity choice: separate
  relations give per-field deltas and per-field reads; one struct gives
  one record that changes as a whole. Reading several relations as one
  slice is the reader's choice (combined form), not the definer's.
- The shape (position profile, FD contract, fold policy) is a static
  property of the relation. Every head contributing to a relation must
  agree on it (§9).
- `sig == X` is legal only when `sig` ends in a bare segment. A relation
  whose last segment carries a key argument needs one more bare segment
  to have a value: `r.fib(v.N).value == v.R`, not `r.fib(v.N) == v.R`.

History. Earlier versions had an FD marker `v == X` legal on any
position, an *anonymous* trailing position (`fib(v.N) == v.R`) and
*composite records* with several FD positions in one signature. All
three are removed: one FD position, last, named by its bare segment,
spelled only by `sig == X`. The any-position marker had been introduced
so that argument order carried no meaning; with a single trailing FD
position the only order that matters is "last", and that is fixed by
the segment being bare, not by textual position among arguments.
Composite records lost their one distinctive property, one reactivity
unit, to the combined form on the read side, and forced readers to spell
out every position (`.subtotal(v).discount == v.D`) to read one.

### Relation identity (settled)

A relation is identified by its segment names **plus** which segments
carry an argument. Hence:

- `order(O).fulfillment_delayed` (one position) and
  `order(O).fulfillment_delayed == True` (two positions, the second being
  the argument of `fulfillment_delayed`) are *different* relations.
- `order(O).subtotal == S` and `order(O).subtotal(S)` are the *same*
  relation.
- `fib(N).value == R` and `fib(N).value(R)` are the *same* relation.
- Whether the last position carries an FD contract is *not* part of the
  identity; it is a contract on the one relation with that identity.

Rejected: a trie or any hierarchical store keyed by prefix; an "object"
identity for `r.order(A)` that `r.order(A).x` attaches attributes to. Every
relation is its own storage (per slice); prefixes mean nothing to the
engine.

### Value structs (settled)

Compound data in v0 is **value structs**: any immutable, hashable Python
compound value (tuple, `NamedTuple`, frozen dataclass, frozenset). A
struct is identified by its contents, exactly like a record: two
derivations producing equal structs produce the same value. No engine
identity, no interning (an optimization if memory says so), no minting.

- **Where they appear.** As the value of an FD position (a bundle that
  changes as a whole, replacing the removed composite record); as a key
  position (a compound key in one slot); as fold elements
  (`setof(Line(item=v.I, qty=v.Q))`); as mutations, errors and effects
  (§11), which are value structs already.
- **Building and destructuring is one expression goal**, planned by
  mode like `v.N - 1 == v.N1`:

  ```python
  v.Rt == Route(from_=v.F, to_=v.T, date=v.D)
  ```

  All fields bound, `Rt` free: build, ≤1. `Rt` bound: destructure,
  binding the free fields and checking the bound ones, ≤1; a value of
  another shape fails the match (no solution, not an error). `Rt` and a
  field both free: unbindable, mode error naming the variable. The
  constructor is a Python callable known at definition time and the
  field list is in the text, so the shape is static; the goal is a
  segment step (§8), no slice, no subscription.
- **Field access** `v.Rt.date` on a bound variable is a pure expression,
  captured like any `v` expression.
- **A struct in a key position is one position.** Binding is all or
  nothing at the mode level; a lookup by one field is an index over the
  slice (§6), not a keyed slice. Keys should be structs of stable
  identifiers; volatile data belongs in values.
- **A struct in a value position is one record.** A change to any field
  is a change of the record. For per-field reactivity use several
  relations (multi-value head).
- **Leaves stay flat** in v0. A mapping exposing several columns as one
  struct (SQLAlchemy `composite()`) is a later bridge.
- Termination: no worse than arithmetic. Datalog bans function symbols
  for finiteness; `v.N - 1` gave that up already, and bounded demand is
  what keeps evaluation finite.

**Not in v0**: structs with identity (a handle standing for "the group
of relations under prefix P with key K", families of such handles, and
late-bound reads through a handle). Discussed, deferred: §14.

---

## 4. Body syntax (settled)

Forms of a relation application in a rule body. Each form is about the
*position* of a thing in the signature, not about whether the definer
made it a key or a value.

| form | meaning |
|---|---|
| `.seg(v.X)` | bind a position; asserts nothing |
| `sig == v.X` | fill the bare trailing segment, asserting its FD |
| `seg=v.X` (keyword, combined form) | same as `_r.seg == v.X` |
| bare trailing segment | existence check; the segment is only a name |

Details:

- `(v.X)` is legal on any position, including the FD position. Reading
  the FD position with `(v.X)` simply asserts nothing.
- `sig == v.X` is an **assertion** that the filled position is
  functionally determined by the key positions. It is legal iff the
  engine can guarantee that: a declared FD contract (§5), a mapping-level
  uniqueness declaration for a leaf (§7), or single-rule exact
  propagation (§6). Otherwise it is a static error naming the fix
  ("`profile` is not functionally determined by `order`; use
  `profile(v.C)`").
- The assertion says nothing about modes. `r.order(v.O).uid == "abc"`
  with `O` free is a lookup by uid and is served like `uid("abc")` would
  be.
- RHS of `sig ==` is restricted to a variable or a literal. Folds
  (`== sum(...)`) are head-only. Value structs are built and taken apart
  by a separate expression goal (§3).
- `== v.X` after a signature ending in a bare segment *defined* bare
  (e.g. `order(O).fulfillment_delayed == v.Flag`) refers to a different
  relation, `order.fulfillment_delayed` with an argument, which is
  normally undefined; see §10 for how that is reported.
- A bare trailing segment on a relation whose only remaining position is
  the FD position (`r.order(v.O).subtotal`) is an existence check.
  Reading a relation with an FD position without caring about it binds
  it to `_`.

### Combined form (settled)

```python
r.order(v.Order)(
    _r.fulfillment_delayed,
    _r.would_cost_at_sale(v.Sale) == v.Price_at_Sale,
    uid=v.Order_UID,
    created_at=v.Order_Creation_Datetime,
    subtotal=v.Subtotal,
    customer_profile=v.Customer,
)
```

- Positional items are `_r` signatures (`_r.x(...)`, `_r.x == ...`,
  `_r.x`), i.e. signature continuations; use `_r`, not `r`, for
  suffixes. Nothing else is legal as a positional item.
- Keyword items `name=v.X` append a bare segment `name` and fill its
  argument, asserting the FD (identical to `_r.name == v.X`).
- A keyword-only call on a bare segment is the combined form on the
  signature so far: `r.order(v.O).insurance(net=v.N, fee=v.F)` reads
  `order.insurance.net` and `order.insurance.fee` as one slice. This is
  unambiguous since a segment takes exactly one positional argument.
- **Parentheses mean one slice, commas mean several.** The combined form
  is one relation application: one plan step, one slice identity. For a
  leaf it becomes one SQL query with all filters; for derived relations one
  materialized anonymous conjunctive view. Separate comma-separated
  subgoals are separate slices and the planner does **not** merge them.
  This is how a programmer controls "filter in SQL" versus "load, then
  filter in Python".

### `exists(...)` subgoal (settled)

`exists(g1, g2, ...)` is an ordinary body conjunct, not a wrapper around
the whole body. Bare `v` in an argument is the wildcard.

```python
r += (r.customer(v.C).has_orders) <= (exists(r.order(v).customer(v.C)))
```

- **Not required.** Implicit projection (a body variable absent from the
  head) stays legal and is correct by support count (§8). Duplicates can
  arise only from projection or from several rules, and most projection
  is harmless (FD-chained variables) or cannot be wrapped (`customer(C)
  .bought(P) <= order(O).customer(C), order(O).item(P)` projects `O` but
  `P` must escape). So "projection requires `exists`" is not a rule.
- **Scoping.** *Escaping* variables occur elsewhere in the rule (head or
  other subgoals); *local* variables occur only inside. Computed
  statically from the `v.X` objects.
- **Meaning.** An anonymous relation whose positions are the escaping
  variables, defined by the inner conjunction with locals projected out
  and deduplicated. It is a slice of its own (certificate, version chain,
  `subscribers`), shared across outer solutions with the same parameters,
  and a **slice boundary**: the planner never merges its body into the
  outer join. The user gets the memoization and the cost, exactly as
  with a named helper relation.
- **Modes fall out.** Escaping variables bound at that plan point are
  parameters, free ones are generated: `exists(r.order(v).customer(v.C))`
  with `C` free enumerates distinct customers having orders; with `C`
  bound it is a check. Servability comes from the inner body's plan.
- **Nodes.** One outer node per outer solution subscribes to the
  anonymous slice; never one per inner solution. Memory is proportional
  to customers, not orders. The delta walk is "count crossed zero".
- **Planning.** A semi-join: stop at the first inner solution; for a leaf
  no need to fetch all records.
- **Negation** is `not_(g1, g2, ...)`, the same anonymous slice with
  the same scoping (i.e. `~exists(...)`), with the safety rule that all
  escaping variables must be bound at that point: it filters, never
  generates. Cycles through negation: §8.
- Same plan-step type as the combined form (§4): `r.order(v.O)(_r.a,
  _r.b == v.X)` is `exists` over a conjunction sharing a key prefix; only
  the spelling differs.
- Possible later lint: "every variable of this subgoal is projected out
  and unused; consider `exists`".

### Control flow: `and_`, `or_`, `case/when/then/else_` (settled)

Goal: innate logical consistency and brevity, while real-world
conditional logic (abundant) stays expressible without five levels of
and/or nesting.

- **Tuple is `and_`, everywhere.** A tuple of goals is a conjunction
  inside a body, inside `or_`, inside `when(...)`, `then(...)`,
  `else_(...)`, `exists(...)`, `not_(...)`. Tuples and `and_` are **pure
  grouping, flattened**: `(G1, (G2, G3), G4)` is four conjuncts, one
  linear plan, no slice. `and_` exists as the name of what a tuple means
  (empty conjunction `and_()`, programmatic `and_(*goals)`, docs) and
  should almost never appear in rule text.
- **Slice boundaries always carry a word**: combined form (keyed case),
  `exists(...)` (check), `when(...)` (condition). Parentheses with no word
  in front never cost anything. Rejected: `and_(...)` meaning "one slice"
  while a tuple means grouping; that would make `and_` and `exists` the
  same construct under two names.
- **`or_(A, B, ...)`**: union of solutions with the prefix shared.
  `(G1, G2, or_(A, B))` is exactly the two rules `G1, G2, A` and
  `G1, G2, B`, except the nodes for `G1, G2` are evaluated once and the
  tree forks below them. Each disjunct is a linear sub-plan with its own
  contribution point (§8). Duplicates across disjuncts are support-count
  like duplicates across rules. Variables bound in only some disjuncts
  are local to them; the bound set after `or_` is the intersection; a
  head variable missing from a disjunct is a definition error naming the
  disjunct. One name only: no `merge`/`fork` aliases (they describe the
  implementation, not the meaning). `or_((G1, G2), (G3, G4))` is two
  levels for two logical levels.
- **Rejected: `branch(...)`** as tail-capturing sugar (`G1, branch(A),
  G4` meaning `G1, or_(A, G4)`). Everything *after* it is the else,
  which reads as the opposite of what it does; two in a record is a flat
  `or_` spelled confusingly; `or_` of tuples is the same length and says
  what it means.
- **`case(when(C...).then(B...), ..., else_(B...))`**: if/elif/else.
  SQL `CASE WHEN ... THEN ... ELSE`, familiar to ORM users; `case` is
  only a soft keyword so it is usable bare.

  ```python
  case(
      when(r.order(v.O).state == "cancelled").then(
          r.price == 0,
      ),
      when(r.order(v.O).discount(v.D)).then(
          v.Base * (1 - v.D) == v.P,
          r.price == v.P,
      ),
      else_(
          r.price == v.Base,
      ),
  )
  ```

  - **The condition decides**, not the whole branch: per incoming env,
    if `C1` has solutions, branch 1 is taken for each of them; a failing
    body yields nothing and does not fall through. (Prolog `*->`.) The
    whole-branch variant ("fall through if `(C1, B1)` has no solutions")
    was rejected: a cancelled order with a missing refund record must yield
    no price, not the discounted one. That variant is what "first" would
    suggest, which is why `first_branch` was dropped as a name.
  - `when(...)` holds exactly one slice, like the combined form; a
    compound condition `when(C1, C2)` is one slice, which is what the
    non-emptiness subscription needs. Bindings from the condition flow
    into the body. `else_` is optional; without it, no branch taken
    means no solution.
  - **Engine support**, same shape as `exists`: each condition is a
    slice, shared and memoized per parameters. A node at the `case`
    step checks conditions in order and subscribes only to slices 1..j,
    j being the first non-empty one. Slice i < j becomes non-empty:
    dismantle branch j, spawn branch i. Slice j empties: continue at
    j+1. Slice j changes but stays non-empty: ordinary delta walk into
    branch j's subtree. One node and at most j subscriptions per env,
    versus n² negation subgoals in the desugaring
    `or_((C1, B1), (not_(exists(C1)), C2, B2), ...)`. Errors can name the
    branch.
  - `case` is negation in disguise: its conditions fall under the same
    stratification rule as `not_` (no cycle through the relation being
    defined).
  - Within one rule it makes branches exclusive per env; that does not by
    itself guarantee the FD across envs; the head contract check stays.
  - Standalone `when(...).then(...)` outside `case` is just `(C, B)`; the
    builder rejects it (and a `when` without `then`) with a message.
  - No rule-level "first rule wins" construct. Overlapping rules for an
    FD relation are an FD violation (checked every wave, §5); an author
    who wants one alternative to take precedence writes one rule with
    `case`. Cross-rule precedence was rejected: the reader of one rule
    could not see that another module overrides it.
- **Spelling rejected for the condition/body split**: operators
  (`C >> B`, `C | B`: they bind tighter than `==`, so every condition
  using the `==` sugar would need its own parentheses, and `>>` was
  removed deliberately); flat alternating lists (`C1, then(B1), C2,
  ...`: structure only in the reader's head, unformattable); method
  chains (`if_(C)(B).elif_(C)(B).else_(B)`: formats badly inside a
  tuple of goals); call-on-call `when(C)(B)` (the hinge wraps as `)(`,
  and a second parentheses already means "continue the signature" on
  relations). `.then(` wraps as `).then(` and names the body.
- Naming family: `and_`, `or_`, `not_`, `else_` (Python keywords with
  underscore), `case`, `when`, `then`, `exists` (bare).

---

## 5. Head syntax and the FD contract (settled)

```python
# key-only relation
r += (r.city(v.City).capital) <= (...)

# FD position: the bare trailing segment filled by ==; key is Order
r += (r.order(v.Order).subtotal == v.Sub) <= (...)

# two keys, one FD position
r += (r.product(v.Prod).at(v.Date).costs == v.Price) <= (...)

# multi-value head ("hydra"): two relations, order.subtotal and
# order.discount, from one body evaluation; keyword = FD position
r += (r.order(v.Order)(subtotal=v.Sub, discount=v.Dis)) <= (...)

# folds, one per relation of a multi-value head
r += (
    r.order(v.Order)(
        subtotal=sum(v.Item_Price),
        items=setof(v.Item),
    )
) <= (...)
```

- An FD position is declared at the head by `sig == X` or by the keyword
  form of the combined form (§3, §4). `v == X` inside an argument, `>>`
  and `out(...)` are gone.
- Heads are always parenthesized: `(head) <= (body)`. This is needed for
  the `sig == X` spelling (Python would otherwise chain `a == b <= c` as
  a comparison), and heads rarely fit on one line anyway, so the
  formatter would wrap them that way regardless.
- A multi-value head (keyword items, informally a *hydra*) is one rule
  instance with several head contributions to several relations (one
  body evaluation); otherwise it is the same as separate rules. Each
  relation has its own slices, deltas and fold. There is no relation
  with several FD positions (§3).
- `r.order(v.O).subtotal == v.S` at the head yields the same records as
  `r.order(v.O).subtotal(v.S)` would, plus the contract. The contract has
  three consequences:
  1. **Enforced.** Two rule instances deriving different values for the
     same keys is a definition error naming both instances (subject to
     the fold, below).
  2. **Assertable at consumer sites.** Body `v ==` / keyword reads are
     legal on this position because of the declaration.
  3. **Folds and delta shape attach here.** A change on such a record is an
     update on the same key rather than remove plus add.
- The FD is one-directional. It says nothing about how many keys share a
  value, and nothing about which modes are servable (§6).
- Multiple rules for an FD relation are fine; mutual exclusivity is the
  definer's claim, checked at derivation time on every wave. The planner
  trusts the declared FD for cardinality because it is enforced.
- Fold policies (per FD position, part of the contract):
  - `plain` (default): any second contribution for the same keys is an
    error.
  - `same`: contributions must agree, else error.
  - `bag`, `sum`, `count`, `setof` (and similar): contributions combine
    into one value; not an FD violation. Each body solution is one
    contribution (§8, support counts).

Rejected: explicit `unique(...)` / `r.x()[:] = UNIQUE` declarations as
the general FD mechanism. The head `v ==` marker is the only FD
declaration in v0.
`unique(...)` remains a possible later escape hatch.

### Why declare `==` at all, if the engine infers ≤1 (settled)

Inferred ≤1 (single-rule propagation, §6) and a declared FD are different
kinds of knowledge, and both are used: single-rule propagation already lets
consumers write `==` with no declaration. The declaration earns its place
in four situations:

1. **Inference cannot prove it.** Several rules meant to be mutually
   exclusive are not provable ≤1 statically; neither is a single rule
   whose ≤1 rests on an unstated data invariant. The declaration turns
   "I believe this" into a runtime check on every wave, the only kind of
   guarantee available there.
2. **Blame placement.** Without a declaration, changing a body from ≤1 to
   generator errors at every consumer's `==`, far from the change. With
   it, the error is at the definition, on the derivation that violated
   the contract.
3. **Stability under redefinition.** Inferred ≤1 is a property of the
   current body. A declared FD is a property of the relation, so
   consumers, deltas and folds depend on something that does not move
   when someone edits a body.
4. **Folds and update-shaped deltas** need the key/value split stated;
   combining contributions per key is meaningless without knowing which
   position is the value.
5. **Planning firewall.** Inferred cardinality is a planning input: ≤1
   steps are scheduled as immediate probes, generators as iteration
   points that create nodes. When a distant change flips a relation
   from ≤1 to generator, every relation whose inferred ≤1 depended on it
   flips too, transitively; every consumer using `(v.Var)` on such a
   position keeps its meaning but is replanned for that mode and has its
   nodes rebuilt (a probe node and a generator's child nodes have
   different shapes); every consumer using `==` there errors instead. The
   reverse flip, generator to ≤1, is only a missed optimization and is
   picked up lazily. The cascade is bounded: plans are memoized per
   (rule, mode) and rebuilt on next demand, nodes are disposable per
   plan and rebuilt from slices, slices survive. A declared FD pins the
   cardinality of that position, so changes behind it cannot ripple
   through consumers' plans.

Rule of thumb for users: declare `==` at the head when you want the FD
enforced, or when you use a fold. Otherwise, if a single rule lets the
engine prove ≤1, consumers may still assert it, and only the check is
lost.

---

## 6. Modes and cardinality (settled)

- A relation application is planned in a mode; each mode of a relation may
  or may not be servable. Unservable modes are static errors that name the
  definition, the use, and the unbindable variable.
- Reverse modes on an FD position (e.g. `-O +C` on `order.customer_profile`
  or `order.subtotal`) are **ordinary mode servability**, not forbidden:
  - leaf: served iff the mapping declares the column indexed (WHERE
    pushdown); otherwise a mode error, or a scan if the table is declared
    loadable whole;
  - derived: served iff the defining rules have a plan with the earlier
    positions free and the last bound, either by pushing the bound value
    into the body, or by enumerating the relation and attaching an
    **index over the slice** (identity = (base slice, indexed position);
    no own certificate; complete iff the base is; dies with it). The
    planner chooses by cost.
  This retires the older principle "values never bind / never form a
  slice identity". What survives of it: the FD contract, and the leaf
  mapping's independent `indexed` flag.
- Cardinality (≤1) sources in v0, computed per (relation, mode):
  - declared FD position with all key positions bound;
  - leaf mapping: schema (PK, UNIQUE, FK) plus application-level
    uniqueness declared on the mapping, trusted and checked at read time
    (a ≤1 probe seeing two records raises);
  - single-rule exact propagation through the body (bound-to-free path all
    ≤1 steps ⇒ ≤1);
  - all positions bound ⇒ membership check, ≤1.
- Multi-rule derived key relations are generators in any mode with a free
  position, unless an FD contract covers it.
- Later, not v0: Mercury-style mode/determinism declarations, user cost
  hints, heuristics.
- Head key bound via an FD read in the body (`r.region(v.R).country ==
  v.X` where `X` is a head key already bound): the bound key becomes a
  check at that position; scan if that is the only route; mode error if a
  leaf forbids it.

### No mode declarations (settled)

Explicit mode declarations, per rule or per relation, were considered
early and rejected. Reasoning:

- A mode of a derived relation is servable iff every rule for it can be
  planned in that mode, and a rule can be planned iff some ordering of
  its subgoals makes each subgoal's mode servable. That is a search over
  orderings and a conjunction over rules, which is exactly what the
  planner computes. A hand-written declaration is either redundant with
  the planner's answer or wrong, and under live redefinition it goes
  wrong silently, because the true set of modes moves whenever any body
  or leaf mapping changes.
- Mercury needs declarations because it compiles each mode to a separate
  procedure ahead of time with no runtime planning. Mode masks, mode
  combination and instantiation lattices exist to let a compiler reason
  without demand. Demand-driven per-(rule, mode) planning makes them
  unnecessary.
- What replaced them: leaves report servable modes with cost and
  cardinality (the only place binding capability is a fact about the
  world rather than a derived property); planning per (rule, mode),
  memoized, with errors naming the definition, the use and the
  unbindable variable; and the one surviving declaration, `==`, which is
  about cardinality, not bindings, and works because it is a property of
  the relation's contents, checkable at runtime and independent of
  evaluation strategy.
- What is lost: an unservable mode is discovered at first demand, not at
  load time, and a rule carries no statement of intended use.
- Open, later: a mode *assertion* (not a declaration), e.g.
  `r.check(r.order(v.O).customer_profile, "-O +C")` or a lint-driven
  equivalent. It defines nothing; it asks the planner to plan that mode
  eagerly at load time so the error surfaces in the editor instead of at
  first demand, and it documents intended use. It cannot disagree with
  the planner because the planner answers it.

### Per-rule servability (settled)

- A relation is the union of its rules. If one rule can serve mode M and
  another cannot, the relation is **unservable in M** (mode error).
  Serving M from the rules that fit would return an incomplete slice with
  a certificate that lies; refused.
- "A rule cannot serve M" is narrow: before giving up, the planner tries
  the rule in a weaker mode (fewer positions bound) and filters or
  indexes the result. If `r2` cannot bind `C` but can enumerate all its
  records, `-O +C` is served for `r2` by enumeration plus an index over that
  slice, at enumeration cost. A rule is truly unservable only when no
  weaker mode is servable either, typically because a leaf refuses
  whole-table loading.
- Each rule keeps its own plan for M (the same subgoal may run in
  different modes in different rules); the relation's slice in M is the
  union of the per-rule results.
- Errors name the relation, the mode, the offending rule and the variable
  it cannot bind.
- Live redefinition: the demanded modes of a relation are known from the
  memoized plans, so an incoming rule that cannot serve one of them is
  reported at the rule, naming the mode and a consumer that demands it,
  by the same blame-placement principle as head agreement (§9). Whether
  the rule is rejected or the consumers' slices go erroneous until one
  side is fixed is open; leaning to reject at the incoming rule.

---

## 7. Leaf (mapped / ORM) relations (settled)

Leaves are a specially implemented relation family. Above the leaf protocol
the engine is uniform; leaves are relations with plans and slices like any
other, but their plans are SQL and they are the source of deltas rather
than consumers of them.

- **Mapping per column**, two independent flags: `indexed` (bound lookups
  by this column are pushed to SQL as WHERE and form slices) and `FD` /
  unique (a ≤1 guarantee, enabling body `==`). A FK column such as
  `ticket.order_id` normally has both; a plain non-indexed column has
  neither; `uid` has both plus reverse uniqueness.
- Mode service: bound indexed columns become WHERE clauses; all positions
  free is refused unless the table is declared loadable whole. Mode errors
  name the fix ("map `order` as indexed").
- Cardinality per mode from schema plus mapping declarations.
- Conglomerate subgoals: the combined form over one table is one query.
- A **leaf fetch certifies every `+T` column slice** of the fetched records at
  once (columns-eager as certification); later column probes for those
  records are memory reads. Probes missing `T` are PK lookups batched per
  wave.
- Flush integration: wave writes go through the ORM session; flush returns
  records that feed the leaf's version chains; real PKs exist before the next
  wave. Single writer; no CDC.
- The facade / object API reads ≤1 modes either way.

### Eager loading (settled in outline)

"Eager loads": when a leaf generator fetches records, also select what
the consumers of the produced values will read, to minimize queries.
Two layers, answering "when" differently.

- **Reactive batching, per wave, always on.** No prediction. The work
  queue (§8) parks every node that needs a leaf record and flushes one
  query per leaf relation when nothing else can run: a wave-3 rule
  reading `.first_name` for a thousand profile revisions is one
  `WHERE id IN (...)`. Context-free, always correct, turns N+1 into 2.
  Granularity is the pull, i.e. the wave: a demand appearing at wave 3
  cannot be folded into a query that ran at wave 0.
- **Predictive prefetch, per chain, static.** Under epochs there is one
  DB read per leaf key per run, at epoch 0; every later wave's read of
  the same key aliases down to it. So the question "what to select when
  `ticket(42)` is first fetched" is "every column any link of the chain
  reads on a `ticket(+T)` slice", independent of which wave asks. With
  the chain-wide view the first fetch loads it all and later waves hit;
  without it, a wave-1 demand for `ticket(+42).seat` misses at epoch 0
  and costs a round trip per wave. Prefetching is materializing keyed
  leaf column slices preemptively (a leaf fetch certifies all `+T`
  column slices, above); an unneeded column is cheap garbage.
  Over-approximation is safe; the analysis depends on the goal's
  *shape* (rules, modes, chain of links), not on data, so it is computed
  once per chain shape, cached with the plans, invalidated with them.

**The analysis: use sets, computed top-down from the chain's goals.**

- Planning already does the descent: plans are made per (rule, mode) on
  demand from the root goals (the chain's mutators). The set of plans
  existing after planning the chain *is* the reachable graph; the full
  program closure is never built (program-wide is only the fallback for
  ad-hoc goals with no chain, and it over-fetches: every column any
  consumer of `order(+O).ticket(-T)` ever reads, for every ticket).
- **Use set** per (relation, mode, position), flowing bottom-up over the
  reachable graph: a variable's use set inside a plan is the leaf columns
  it is used to look up directly (`ticket(+T).seat`) ∪ the use sets of
  the head positions it is projected into ∪ the use sets of the bound
  positions of subgoals it is passed to (the callee's entry). A head
  position's use set is the union over all consumer applications in the
  reachable graph of the variable bound there. One bottom-up pass on a
  DAG, a fixpoint under recursion (small graph).
- A **load point** is a leaf generator inside a plan, e.g.
  `r.ticket(v.T).order_id == v.O_id` inside the rule for
  `order(v.O).ticket(v.T)`; it prefetches the use set of the variable it
  produces, i.e. of position `T` of `order.ticket` in mode `+O -T`:
  "consumers of that relation, transitively". Merging across mutators is
  automatic: mutators reaching the same (rule, mode) share one plan and
  one load point, whose consumers accumulate on that plan object.
- Coarse variant (union per leaf relation over the chain, by relation
  not by flow) is simpler; the flow-precise variant above narrows it
  when different loads feed different consumers.

**Keeping over-fetch in check**, in order:

1. Root at the chain (above); a chain like "cancel ticket 42" reaches a
   small subset of the rules over tickets.
2. The mapping marks wide or rarely used columns (text, JSON, blobs)
   "never prefetch", like deferred ORM columns; they come through the
   reactive batch when read.
3. Record-group storage (§8) makes a prefetched column a slot per key
   rather than a slice object per (record, column). If prefetch is used
   seriously, record-group storage stops being optional.

**Conditionals.** The static use set through `case` is the union over
branches, so a column read only in an untaken branch is fetched. Default
heuristic: union through `case` for **same-record columns** (an extra
small column beats a round trip; "never prefetch" handles the wide ones),
**cut at `case` for anything keyed by other values** (related records:
new keys, batched per wave anyway, and a join for records that will not
take the branch). Same for `or_` and the witness scan of `exists`.
A knob on the analysis, not semantics; revisit with numbers.

Related records (`order.customer.profile`) are the same one level up:
predicted as a join folded into the first query, or batched by IN-list at
the wave where the key values appear.

---

## 8. Slices, incremental maintenance, retraction (settled)

### Slice

Storage is per slice, i.e. per (relation, mode, bound values). A slice
holds: records; a completeness certificate (empty-but-certified is knowledge);
a version chain of changes; `subscribers: set[node]`, the join nodes
that read the slice. No multi-column cell in the core.

### Subscription model (settled)

Slice level only. The producer keeps `subscribers`, a set of the nodes
(join nodes) that iterate or probe it; subscribe and unsubscribe are O(1)
set operations. The consumer keeps, per node, the observed version of
each input slice and `children: dict[input_record, node]`, the subtree
spawned per record. Deltas are consumed by the subscribed nodes, which do
the dropping of subtrees and the deriving of new ones themselves.

Rejected: a producer-side per-record index `dependents: dict[record,
list[node]]`. It was inherited from a design with coarse slices and is
redundant with keyed slices: a probe by `R` does not subscribe to a big
`region.country` slice and pick out its key, it demands the slice
`region(+R).country` and subscribes to that. Slice identity already
partitions consumers by key, so every subscriber of a slice wants every
delta of that slice and there is nothing for a record-keyed index to
select. Unsubscribing would also have been a linear search in a per-record
list.

- A ≤1 node holds a single child slot instead of a dict; a check node
  holds nothing; a generator with a residual filter holds children for
  the passing records only.
- **Misses** need no special registration: a probe that found nothing
  subscribed to a certified-empty keyed slice, and the record's arrival is
  an ordinary delta on it.
- The one subscriber that sees deltas it does not need is a node served
  by a weaker mode plus filter (a `+O +C` probe on the `+O` slice); it
  filters the delta, and the slice is small by construction.
- Invalidation marks walk `subscribers` to the nodes' owning slices.

### Records, deduplication and support counts (settled)

- Every relation has **set semantics**. With no FD positions, a record *is*
  its tuple of key values; within a slice the bound positions are fixed,
  so the record is identified by the free-position values. Two derivations
  producing the same tuple are the same record. No object identity, no
  ordering, no hidden id.
- A rule body yields a set of **solutions**, one per distinct binding of
  *all* body variables, including those projected out of the head and
  those bound to `_`. Subgoal slices are deduplicated, so this set is
  well-defined and matches SQL join-then-project.
- For a plain relation each solution supports the head record it maps to.
  The slice keeps a **support count** per record: the number of solutions,
  across all rules, mapping to that record. Retracting one derivation
  decrements; the record disappears (and a delta is emitted) only when the
  count reaches zero. This is the netting used by version deltas (§8,
  invalidation).
- For a fold, each solution contributes one term at its key. Two tickets
  with the same price are two solutions (they differ in `T`), so `sum`
  counts both. The support count is thus the `count` fold applied
  implicitly at every non-FD relation; `bag`, `sum`, `setof` are the same
  machinery with another combining function. One model for duplicates:
  dedupe at the record level, count or fold at the solution level.
- The support count is **internal**. Users see a record present or absent
  and must not rely on duplicates being observable; the number of
  derivations is obtained with an explicit `count` fold.

### Contribution point and dedup elision (settled)

Where in a linear plan the head contribution is made, and when the
dedup probe can be skipped.

- **Contribution point.** Walking the plan steps in order, at some step
  k every head variable (and every fold term) is bound. The head
  contribution is attached to the node at step k, not to the leaves of
  the search tree. Steps k+1..n cannot change the head tuple; they only
  decide whether, and for multiplicity folds how many times, this node
  contributes.
- **Tail.** Each step-k node keeps one counter: the number of live
  solutions of the tail. For a plain relation the contribution is present
  iff the counter is positive; a tail delta touches the counter and the
  head is notified only on a zero crossing; dismantling a step-k node
  removes one support in one operation. The tail is planned as a
  semi-join (stop at the first solution) for plain relations and for
  `same`/`setof` folds. For `count`/`sum`/`bag` every solution counts, so
  the tail is enumerated and the counter is the contribution's weight;
  semantics stay "one term per solution", independent of plan order.
- **Where duplicates come from.** Records of one slice are distinct, but two
  records may agree on the head variables and differ only in projected
  positions. So a head-tuple duplicate always originates at a generator
  that **branches on a projected variable**: a record position not
  FD-determined by the variables already bound and not a head variable.
  Two cases:
  - the projected variable is **dead** afterwards (never a bound position
    of a later step): the branches are identical from there on and demand
    the same slices. The planner turns that generator into a projection
    onto its live variables with a count, i.e. an automatic `exists` at
    that step;
  - the projected variable is **live**: the branches are different
    computations (different slices downstream) that may still agree on
    the head tuple. Nothing on the path can know before the tuple is
    complete, so the step-k node probes the slice's record dict by head
    tuple and inserts or bumps the support count. That dict exists anyway
    (storage, deltas), so the probe is the storage write itself, once
    per step-k node rather than once per solution.
- **Elision.** If no step before k branches on a projected variable, every
  step-k node has a distinct head tuple, the insert is guaranteed new
  and no count is kept. The planner decides this per plan from the FD
  contracts alone. It is the common case for lookup-shaped rules.

Example, unbound slice `-C -X` of `city.country`:

```python
# A: dedup elided
r += (r.city(v.C).country(v.X)) <= (
    r.city(v.C).region == v.R,
    r.region(v.R).country == v.X,
)
# B: dedup needed
r += (r.city(v.C).country(v.X)) <= (
    r.city(v.C).region(v.R),
    r.region(v.R).country == v.X,
)
```

In A, step 1 reads the unbound slice of `city.region`, records `(C, R)`.
`R` is projected and live, but `C -> R` is declared, so step 1 branches
only on the head variable `C`. Step 2 binds `X`, the contribution
point. Two step-2 nodes differ in `C` or, under one `C`, in `X` (records
of one slice are distinct), so `(C, X)` is always new: plain store.

In B, step 1 may yield `(paris, ile_de_france)` and
`(paris, greater_paris)`, agreeing on `C` and differing only in the
projected `R`. Both branches reach step 2 with different slices and both
may yield `france`: two step-2 nodes, one head tuple `(paris, france)`.
Probe and support count are needed. The `==` in A is what turns `R`
from a branching variable into a determined one.

- **Planner preference** that follows: bind head variables as early as
  possible and push pure filters to the tail, so the tail is as large as
  possible. Hash joins of two slices fit the same scheme; the
  contribution point is the join output that completes the head tuple.

### Nodes, segments and generated code (settled)

**Segments.** A plan for one (rule, mode) is a linear sequence of steps.
Every run of non-generator steps (≤1 lookups, checks, Python
assignments) between two generators, or before the first / after the
last, is one **segment**; a segment ends either in a generator, at the
contribution point, or at the head. A rule mode with no generator is one
segment. Nodes are created at **generator items** only: one node per
record of a generator's input slice, running the segment that follows.
A rule instance with no generator has exactly one node.

**Node fields** (a slotted object; the node *is* the subscription that
sits in `slice.subscribers`; no `functools.partial`, which is opaque and
could not carry the fields below):

- `step`: the plan step this node instantiates. Owns the generated
  function, the variable names for `args`, the input relation and mode,
  and the kind (generator, linear, `case`, `exists`).
- `args`: the live variables after the previous step, positional, in
  plan order: the argument tuple of this segment's function. Only
  variables some later goal, the head, or a fold term still needs (need
  set by liveness analysis); this is the node's memory layout, dead
  variables cost nothing. Re-entry is `step.fn(engine, node, *args)`.
- `observed`: a tuple parallel to the segment's lookup list, entry `i`
  being `(slice, version)` for lookup `i`, hits and misses alike (a miss
  is a certified-empty keyed slice). Positional, not a dict: the lookups
  are fixed by the plan, and the slice object is stored because a re-run
  with other key values may demand another keyed slice for the same
  lookup; old/new subscriptions are diffed on these entries.
- `gen` (generator nodes only): `(slice, version)` of the generator's
  slice, and `children: dict[input_record, node]`, the subtree spawned
  per record of that slice.
- `parent`: the node above, for unlinking from `parent.children` on
  dismantle and for walking upward in a "why" explanation.
- `head` (contribution-point nodes only): the head record this node
  supports, plus `max_in`, `prev_dup`, `next_dup` (§8, justified
  records). Tail nodes below a contribution point carry only `observed`,
  `gen` and `children`; the tail counter lives on the contribution-point
  node.

No env dicts at runtime. `dict(zip(node.step.varnames, node.args))`
reconstructs one on demand for error messages, the debugger and the
"why is this record here" explanation. A debug mode that passes the full
env instead of the need set is worth keeping switchable.

**Pull-time check** is one loop: any `observed` entry behind its slice's
head means re-run the segment; the `gen` entry behind its head means
walk that chain against `children`.

**Re-running a segment** means running it again from its stored `args`:
every lookup in it is redone, the result (head contribution or the call
into the next generator) is diffed against the previous one, and the
subscription set is diffed too, because a changed lookup can change
which keyed slices later lookups demand. A change in the third of five
lookups redoes the other four, dict probes, in exchange for one node and
one call instead of five. Splitting a segment at a chosen lookup is a
planner decision with no semantic effect (the whole-subtree replay knob,
at segment granularity).

**Generated code.** Per (rule, mode), the plan is compiled to Python
source and `compile`d: one function per segment. The env becomes Python
locals, checks become `if`, ≤1 lookups become assignments, a step is one
call. Estimated 3 to 10× per-record gain over a plan interpreter (dict
env, dispatch per node kind), and per-record Python cost is the engine's
main limit, so this is the biggest single lever.

- **Flat functions, not nested closures.** A node must be re-entered
  later with its stored `args`; a closure per node would cost memory,
  could not be inspected, and could not be recreated after a
  redefinition. Flat `step_k(engine, node, *args)` gives the same
  locals-based speed with plain node objects.
- **What stays generic**: nodes, subscriptions, `children`, dismantling,
  version chains, dup lists, SCC and justifier logic, leaf queries,
  `case`/`exists` bookkeeping. Generated code does only the per-record
  work and calls a handful of engine primitives (`demand`, `contribute`,
  `spawn`).
- The planner produces a **plan IR**; codegen is a backend over it. An
  interpreter over the same IR is kept as the debug backend and the
  reference for tests.
- Compile with a filename like `<rule order.subtotal, mode +O>`,
  register the source in `linecache` so tracebacks show the generated
  line, and keep a map from generated line to the goal in the rule so
  blame lands on the user's line.
- `v.X` expressions (`v.Amount > v.Min`) are captured as expression
  trees at definition time and rendered to source; the planner needs
  them as trees anyway.
- Generation is per demanded (rule, mode), lazy and cached, like plans.

**Rebuild on rule or plan change.** The slices using that (rule, mode)
drop that rule's nodes, re-run the new plan, diff the resulting records
against the old ones and publish the net delta; downstream sees an
ordinary delta and is not rebuilt; aliases at other epochs need nothing
until they dissolve. Node trees are per rule, so with several rules for
one relation only the changed rule's nodes are redone and the slice head
nets. A plan depends only on the rule text, the declared shapes of the
relations it reads and the leaf mappings, so a plan change without a
rule change comes only from those, and the same rebuild applies to every
(rule, mode) that read the changed relation. This is the "delta is
everything" version of §8, applied per rule.

### Retraction

- Removed record: each subscribed node finds `children[record]` and
  dismantles that subtree: retract its head contribution, unsubscribe it
  from its input slices, recurse into children.
- ≤1 change: the node re-runs its segment; if it now fails it dismantles
  children and head but stays alive.
- Lazy scheme: a consumer holds a version pointer per input and unchains
  on revalidation, netting the delta per record against its own
  `children`: removed records dismantle, added records spawn child nodes,
  changed ≤1 values re-run the segment.
- Adding a record: recorded in the current version (cancels a pending
  removal); a dirty flag propagates upward, stopping at already-dirty
  nodes. A head write is a new version on the head slice.
- No torn reads: all writes of a wave land before revalidation, and
  consumers revalidate inputs first. Per-field subscriptions are native
  because each relation is its own slice.
- No determinism requirement on evaluation order.

### Invalidation, versions and revalidation (settled)

Usage pattern that drives the design: client code (interactive session,
UI binding, test) registers a **root goal**, i.e. a slice it is
interested in, and expects it to be kept up to date. The live set is
the closure from root goals. Everything outside it is garbage or cache.

Considered and rejected: pure eager push (recompute dependents as
deltas arrive). It needs a strict scheduler to avoid the *diamond*
problem: a change reaching slice `c` via `a` directly and via `a -> b`
would recompute `c` twice, with a glitch state (new `a`, old `b`) in
between that may already have been observed. Push needs heights, SCC
handling and recompute-once bookkeeping. Pull gets all of that from the
recursion order for free.

Also considered: the Salsa scheme (global revision counter, no eager
walk, verify upstream on every pull, memoized per revision). Its eager
cost is O(1) but every pull of a root walks the root's whole upstream
graph once per revision even when nothing changed, which is the wrong
trade for many roots and small changes (the interactive case).

Settled scheme: **eager invalidation, lazy delta-driven recomputation,
pull all roots at commit.**

- **Eager marking walks the slice graph only.** A leaf change advances
  the version of the affected leaf slices (those whose bound key matches
  the changed record, plus the unbound slice). Their dependent slices get a
  "maybe changed" mark, transitively. Individual nodes are not
  visited. Marking is idempotent and **stops at already-marked slices**,
  so between two pulls the graph is walked at most once regardless of
  how many changes arrive; the cost of a commit's invalidation is
  bounded by the number of clean slices that become dirty. Fan-out is
  structural (rules downstream of a relation), not proportional to
  records, except through unbound slices, which are few.
- **Pull at commit.** After a transaction commits, every root goal is
  pulled. A root with no mark in its subtree is skipped. Pulling a
  marked slice first pulls its upstream slices (recursion order gives
  diamond-safety and recompute-once), then revalidates its own nodes.
  Reads between commits see a consistent fixpoint. Restricting the pull
  to roots reachable from what was dirtied is a later optimization that
  does not change the model.
- **Versions and version chains.** A slice keeps a chain of versions;
  each version carries its delta (records added, records removed) relative to
  the previous one. A node subscribes to a slice *at a version*. The
  head delta of a slice is produced by netting (multiplicity counts) the
  head retractions and assertions of its own nodes' dismantles and
  fresh evaluations, so the delta consumed downstream is exactly the
  delta produced upstream: one mechanism end to end.
- **Revalidating a node is walking the chain**, not re-running the
  generator: from the observed version to the head, removed records
  dismantle their child subtrees, added records evaluate fresh, everything
  else is never looked at. Then the node re-subscribes at the head.
  Deltas from several versions are **netted** into one dict before
  applying, so a record added in V+1 and removed in V+3 costs nothing.
  A generator with a residual predicate on top of the slice filters the
  delta with the same predicate.
- **Nodes are bucketed at pull time**, not by the eager walk: a dirty
  slice compares the versions its nodes observed with the upstream
  heads and buckets the stale ones.
- **Per-slice processing is top-down.** Depth in the search tree is the
  plan step, so "topological order" is plan-step order: one bucket of
  stale nodes per plan step, processed in step order. A node whose
  ancestor's delta removed the record it hangs under is dismantled by that
  ancestor (dismantling clears an `alive` flag on the whole subtree
  while unsubscribing it) and is skipped when popped from its bucket.
  Doomed subtrees are never revalidated. A `dirty_below` counter per
  node, to descend only into subtrees containing stale nodes, is an
  optional later optimization of the same scheme.
- **Recursive slices**: a node in S may subscribe to S itself. Top-down
  processing is one pass; the pass repeats to a fixpoint for the SCC.
- **Chain representation and GC.** Versions link forward only, older
  to newer: each version holds its delta, an index (int, for comparisons
  and the cap) and a pointer to the next version. The slice holds only
  the head; a node holds a *reference to the version object* it
  observed, not an int. Advancing a node replaces that reference with
  the head, so when the last node observing an old version advances,
  that version and everything older become unreachable and CPython's
  own refcounting frees them. No min-scan over `subscribers`, no
  per-version counters, no sweep for versions. Explicit refcounts would
  buy only independence from the host's memory management.
- **Cycles.** A subscription cycle (a node of `S` observing `S`) does
  not make the chain cyclic; the node advances each time it consumes
  `S`'s delta during the SCC fixpoint, so at the fixpoint all of `S`'s
  nodes are at the head. A dead slice takes its chain with it; demand
  cycles are the tracing sweep's job (Slice GC, below).
- **Cap and fallback.** A root nobody pulls, or a stuck node (e.g. on
  an erroneous slice), pins the chain behind it. When the chain behind
  the head exceeds N versions, the slice replaces the deltas of versions
  beyond N with a *truncated* marker, leaving the objects linked. A node
  walking into a truncated version takes the **recompute-and-diff**
  fallback (re-run the segment with the stored `args`, diff against
  existing `children` keyed by record), advances, and the chain is freed
  behind it. The same fallback serves a slice rebuilt from scratch (plan
  change, redefinition) and a leaf whose delta is unknown. It is the
  "delta is everything" version, not the main path.
- **Unobserved slices** keep no versions. With `subscribers` empty
  there is nobody to walk a chain: `head` is `None`, and a revalidation,
  if one happens, mutates the record dict in place with no delta. Under
  pull it mostly does not happen: the slice sits dirty as stale cache
  until demanded. When a subscriber arrives the slice is pulled first and
  the head version object is created at that moment, an empty delta the
  new node observes; revalidations append deltas from then on. What
  survives the unobserved period is the records, the certificate and the
  erroneous/alias flags, which is what makes the cache worth keeping.
  Unobserved slices cost nothing beyond the mark. A root that
  unregisters simply stops being pulled; its slices are the stale cache
  and a sweep drops them at leisure. No grace-period machinery. The
  sweep is reachability-based (see "Slice GC" below): `subscribers` is
  a refcount and refcounts fail on demand cycles.
- Proposed, not yet settled: reads from Python inside a transaction
  (e.g. in actions) see the pre-commit fixpoint rather than triggering a
  nested pull; a per-slice version counter is exposed so UI bindings can
  ask "did this change in the last commit" without diffing records.

### Negation, fixpoint and negative cycles (settled)

No stratified evaluation. An incremental engine has no "evaluate from
scratch in stratum order" anyway: every commit is a chaotic revision in
pull order, and a negation node flips both ways when its slice
crosses zero. For a stratifiable program this converges to the perfect
model regardless of order (induction on strata), just with more passes
than stratified scheduling; reimplementing stratum scheduling inside the
delta walk would buy little. Earlier decision confirmed.

The wave cap keeps one job: **actions**. Rule derives, opaque Python
action writes a leaf, rule re-derives is a loop no static analysis can
see; a cap on waves per commit with an error naming the last action is
the tool there. The cap is *not* a semantics device for negation: it
catches oscillation (`p <= not_(p)`) but not the dangerous case
`p <= not_(q), q <= not_(p)`, which settles on `{p}` or `{q}` depending
on evaluation order and reports nothing.

**Dynamic negative-cycle detection** closes that gap, cheaply:

- The negation is one edge, from the outer node into the anonymous
  slice `N` of the `not_(...)` body (parameters bound outside, the rest
  local). Inside `N` the subgoals are demanded positively, as in any
  derived relation. The same holds for a `case` condition and for a
  fold: the *edge* into the slice is non-monotone, the inside is not.
- A non-monotone read needs the slice **complete**; partial contents say
  nothing (a positive read is fine with partial contents, the rest
  arrives in the SCC fixpoint). "Complete" is what the pull provides by
  evaluating `N` to the end before returning.
- Each pull-stack entry (slice whose first computation or revalidation
  has started and not finished; while an SCC iterates, every slice of
  that SCC counts as in progress) records whether it was **entered
  through a non-monotone edge**. When a pull reaches a slice already on
  the stack, look at the stack segment from that slice to the top: if
  any entry in it was entered non-monotonically, it is a negative cycle;
  otherwise ordinary recursion. Positive recursion entirely inside `N`'s
  body never crosses the frame and is allowed.
- Edges are dynamic (bound keys come from data), so the check fires at
  demand time and per key, like undefined relations (§10). This accepts
  locally stratified programs (`even(N) <= not_(even(N-1))`): slices
  form no cycle even though relations do.
- **Relation-level stratification** (a negative/fold edge inside an SCC
  of the rule graph) is a load-time **gutter warning only**, optional,
  nice-to-have: it tells the author early that the possibility exists,
  but it false-positives on locally stratified programs, so it never
  rejects.
- In the parallel form (below) the same check walks the wait-for graph.

Example that closes the loop, welfare counted as income:

```python
r += (r.person(v.P).needs_wellfare) <= (
    r.person(v.P).demanded_wellfare,
    not_(
        r.person(v.P).income_source(v.Source),
        r.income_source(v.Source).amounts_to == v.Amount,
        r.income_source(v.Source).absolute_minimum == v.Min,
        v.Amount > v.Min,
    ),
)
r += (r.person(v.P).income_source("welfare")) <= (
    r.person(v.P).needs_wellfare,
)
```

Pull `needs_wellfare(+p)`; its node enters `N(+p)` non-monotonically;
`N` pulls `income_source(+p)`, which pulls `needs_wellfare(+p)`, on the
stack with `N` between: error, message prints that chain, gutter marks
the `not_`. Without the second rule nothing loops and nothing fires.

### Errors as values (settled)

Requirements, in order: no corrupt data; stay usable when a cycle is
detected (no "stop the planet"); preserve the materialized state so the
fix does not recompute the world.

A detected cycle is a **value**, not an exception. The pull that detects
it does not unwind; it returns an error object that flows through the
graph like data.

- A slice has one more state besides clean / dirty / in progress:
  **erroneous**, holding the error (the cycle chain with the
  non-monotone edge marked for blame). It publishes a version whose
  certificate says "error" instead of "complete". Nothing can read it as
  data: a facade read raises, a negation cannot test emptiness, a
  generator over it yields nothing and propagates the error into its own
  node.
- **No half-applied deltas.** The node that hit the cycle subscribes
  to the erroneous slice and finishes its walk normally; a node's
  observed-version pointer moves only after its walk completes, and the
  walk always completes, with records or with an error. Exceptions were the
  wrong tool precisely because they abort mid-walk.
- **Propagation.** Any slice with an erroneous input is erroneous.
  Slices upstream of the non-monotone edge and unrelated slices stay
  valid. Detection is per key, so only the keys whose data close the
  loop go erroneous; others are served normally. A root whose subtree
  holds an erroneous slice reports the error to its client (UI error
  state for that cell, REPL prints the chain).
- **State preserved.** An erroneous slice keeps its nodes and its
  last-good records, unreadable. The error is an entry on the version chain:
  `V(records X) -> V+1(error, X retained) -> V+2(ok, delta relative to X)`.
  The fix (normally a redefinition of one rule on the cycle) dirties that
  relation's slices through live loading; the next pull finds no
  in-progress slice, and revalidation is the ordinary delta walk from
  the retained nodes. Downstream erroneous slices consume
  `V+1 -> V+2` as a normal delta from X. Nothing outside the cycle is
  recomputed; inside it only what the fix changed.
- "Erroneous" is in effect a third truth value, what well-founded
  semantics would assign; we report it instead of computing with it.
  Silent well-founded semantics later would be a policy change on the
  same state, not a new mechanism.

### Positive recursion under retraction (settled)

Support counts are correct only for non-recursive rules. With
`p(X) <= leaf(X)`, `p(X) <= q(X)`, `q(X) <= p(X)` and `leaf = {a}`:

1. `p(a)` from `leaf(a)`: node R1, support count 1.
2. `q(a)` from `p(a)`: node R2.
3. `p(a)` from `q(a)`: node R3, support count of `p(a)` is 2.

Retract `leaf(a)`: R1 is dismantled, the count drops to 1, still
positive, **no delta is emitted**. R3 supports `p(a)`, R2 supports
`q(a)`, each justified by the other: both records are zombies served with a
valid certificate. A count answers "how many nodes contribute", not
"is any of them justified from outside the loop". Propagating the
decrement instead (bag semantics) fails the other way: multiplicities in
a cycle are infinite, each trip around adds a derivation, counting never
converges.

Options considered:

- **DRed scoped to the SCC**: a record inside a recursive SCC that loses
  *any* node is deleted regardless of count, dependents are dismantled
  transitively within the SCC (over-deletion), then re-derived from the
  nodes whose supports are still live. Known cost: transitive closure
  over-deletes many paths and re-derives most of them.
- **Whole-SCC rebuild**: on any retraction touching an SCC, recompute
  its slices from scratch and diff. Crudest correct option; SCCs are per
  slice (`p(+a)`, `q(+a)`) so usually small, but the all-free
  `path(-X, -Y)` root makes one SCC of the whole relation.
- Per-record tracing GC: rejected as overkill, it is DRed's over-deletion
  without its locality.
- **Ranked justifications via creation timestamps**: chosen, below.
  Per-SCC round numbers were rejected (SCC merges break them); a global
  counter has no such problem and needs no SCC membership.

#### Justified records (settled)

Invariant to keep, instead of "newer than everything it depends on"
(which would need refreshing on every upstream change): **every live
record has one designated justifier node whose inputs are all older
than the record.** Established at creation, checked only at deletion,
never refreshed. Justifier chains are strictly decreasing in time, so
they cannot loop and bottom out at leaves: a record with a valid justifier
is grounded whatever else supports it.

Data, kept for **all** relations, recursive or not (same structures
everywhere; only one check is switched on by the static filter):

- **record**: `ts`, creation timestamp from one global counter, assigned
  when the record is first derived, kept for the record's lifetime, fresh
  value on re-derivation; `head`, pointer to the justifying node,
  which is by convention the head of the record's dup list.
- **The `ts` counter**: one engine-wide int, `ts += 1` on every record
  creation. Per record, not per wave or commit: a record and one derived
  from it in the same wave must differ, or `max_in < ts` fails for a
  grounded justifier and over-deletes. Python ints do not overflow; a
  packed array later uses 64-bit slots. The only property used is
  "strictly increasing with creation order".
- **node** (contribution-point node): `max_in`, the largest `ts` among
  all records **the node's derivation consumed**, cached at creation;
  `prev_dup`, `next_dup`, intrusive doubly-linked list of the nodes
  supporting the same record ("dup" = duplicate supporters). No
  per-record `set` or `list` object; the support count is gone, "dup
  list empty" is the zero-crossing test.
- **What `max_in` covers.** The whole path, not the node's own segment
  only: the generator record each ancestor hangs under and every
  ancestor's lookups are inputs of this derivation too. Incremental:
  `max_in = max(parent.max_in, ts of the node's own inputs)`, so each
  node looks at its own inputs and inherits the rest. Plus the **tail**:
  a contribution exists only because some tail solution exists, and
  that solution's inputs belong to the derivation. Example:
  `p(X) <= leaf(X), q(X)`, `q(X) <= p(X)`, `q(X) <= leaf2(X)`. The
  contribution point of the first rule is after `leaf`, the tail reads
  `q`, and `q(a)`'s `ts` must enter `max_in`. If `q(a)` is later
  deleted and re-derived with a fresh `ts` (say from a `leaf3`), the
  witness changes, `max_in` is recomputed above `p(a).ts`, and `p(a)`
  is re-derived with a fresh `ts` too. Without that, retracting `leaf3`
  would let `q(a)` adopt the back node `q(a) <= p(a)` as justifier (its
  `max_in` is the old `p(a).ts`, below the new `q(a).ts`) and the two
  would hold each other up on nothing. The witness tail solution's
  inputs are used; a lower-`max_in` tail solution that was not the
  witness can cause an over-deletion, repaired by step 3.
- **When `max_in` changes.** Never because a subscribed slice grows: a
  generator node hangs under one specific record (its key in the
  parent's `children`), and new records spawn sibling nodes with their
  own `max_in`; a lookup that starts to hit is a ≤1 change. So `max_in`
  is recomputed exactly when the derivation changes: a segment re-run,
  or a tail witness change on rescan. If the node was a record's `head`
  and the recomputed `max_in` is no longer below the record's `ts`, that
  is a justifier loss (adopt, else delete, cascade, re-derive); a re-run
  node is not assumed grounded because it survived.
- Approximate CPython cost per record: bare small-int count ~0 B; `set`
  ~216 B; `list` ~56 B + 8/node; `__slots__` object with `ts`, `head`
  ~48 B, plus 28 B for a `ts` int above 256 unless packed. Later,
  record-group storage (§8) holds `ts` in a packed array and `head` in a
  parallel list by record slot: 16 B per record, no per-record object.

Events:

1. **Node R created**, contributing to record X. X absent: create with
   `ts = now`, `head = R`, emit `+X`; `now` exceeds every input's `ts`,
   so the invariant holds by construction. X present: link R into the
   dup list under the head. Nothing else, no comparison; R's `max_in`
   may exceed `X.ts`, which only means R can never justify X.
2. **Node R dismantled** (its input record vanished, or its parent was
   dismantled), contributing to X. Unlink R. If R was not `X.head`:
   done, X stays, no delta. If R was `X.head`: **adoption**:
   - relation not in any static cycle: adopt *any* remaining dup. This
     is exactly count semantics; no over-deletion, no re-derive phase.
   - relation in a static cycle: adopt a dup S with `S.max_in < X.ts`
     (move it to the head). None: delete X, emit `-X`, dismantle
     dependent nodes (recursing into this event), keep X's remaining
     dups on a re-derive list.
3. **After the cascade**: every surviving record has a justification that
   passes through nothing deleted, so it is grounded. For each deleted
   record still holding a node whose inputs are all live: recreate with
   fresh `ts`, that node as `head`, emit `+X`, propagate as event 1.

Walk-through: `p(a)` at t1 via `leaf1(a)` (R1), `q(a)` at t2 via
`p(a)` (R2), back node R3 `p(a) <= q(a)` with `max_in = t2`, later
`leaf2(a)` at t5 giving R4 for `p(a)` with `max_in = t5`. Dups of
`p(a)`: R1 (head), R3, R4. Remove `leaf1(a)`: R1 was the head;
R3 (t2) and R4 (t5) both exceed t1, none acceptable; delete `p(a)`;
`q(a)` loses its head R2, no candidates, deleted; R3 goes with it.
Re-derive: R4's input `leaf2(a)` is live: `p(a)` back at t7 with head
R4, `q(a)` at t8, the new back node has `max_in = t8` and joins the
dups without justifying. Over-deletion was one record and its dependent,
not the SCC.

Properties:

- Insertions cost a timestamp. Over-deletion exists (a legitimate
  support that arrived later than the record) but is bounded and repaired
  in step 3; never worse than a whole-SCC rebuild, usually far less.
- **Live redefinition is a flag flip.** In a non-recursive program every
  live record is grounded, so whatever node is its head when a recursive
  rule arrives is a grounded node and stays so while its inputs live
  (the cascade never leaves an ungrounded record alive). No re-timestamping,
  no re-justification; the `ts` test simply starts applying. An old record
  losing its head later may fail the test against its other old dups
  and be over-deleted and re-derived once. Removing the recursive rule
  again is the reverse flip. The static relation-level SCC analysis,
  recomputed at each live load, thus decides three things per relation
  without touching stored state: whether the `ts` test applies, whether
  slices do SCC bookkeeping on the pull stack, the stratification lint.
- **Cascade and re-derive stay inside the slice/SCC.** The two-phase
  "delete to full depth, then add to full depth" is the push/DRed
  picture; here a slice (or SCC) publishes **one netted version** when
  it completes, and a record deleted in the cascade and re-derived is
  absent from that delta. Downstream is not looked at before upstream
  is complete (pull order). Consumers net several versions into one
  per-record delta before walking and apply that merged delta, not
  removals-then-additions, so a record that changed supporters but not
  presence causes no local churn. Internal SCC churn is the bounded
  cost accepted.
- For slices themselves this scheme is wrong: a long-lived slice
  routinely outlives its first demander while newer demanders need it,
  and a timestamp test would drop and recompute it (thrash). Slice
  liveness is memory, not truth: tracing GC (below).

### SCC detection (settled)

Two levels, two roles, no separate algorithm:

- **Slice level detects.** A pull that reaches a slice currently in
  progress has found a cycle; every stack entry from that slice to the
  top belongs to one SCC. Union them (union-find on a small SCC object
  hung off the slice) and continue: incremental Tarjan, the same thing
  XSB does when it completes a group of tabled subgoals together. The
  negative-cycle check (above) is this detection plus one flag on the
  stack entry; both come out of one piece of code.
- **Maintenance is asymmetric and that helps.** New edges merge SCCs
  (union-find, constant time). Vanishing edges could split an SCC;
  union-find cannot undo, and we do not try. A stale, too-large SCC is
  harmless: it only widens the fixpoint iteration and the re-derive
  scan (step 3 above) by a few slices, and the next pull of its members
  runs the stack detection on the current edges and rediscovers the
  true cycles, so the grouping self-corrects when used.
  Over-approximation is safe; under-approximation is the only wrong
  direction.
- **Relation level filters.** The static rule graph says which relations
  sit in a recursive SCC at all. Slices of relations outside any static
  cycle can never be in a slice cycle and skip the SCC bookkeeping
  entirely (the vast majority). The same static graph feeds the
  stratification lint: one load-time analysis, two uses.

### Slice GC (settled)

Slice liveness is **memory, not truth**, which is what makes it cheap.
`subscribers` is a reference count, and `p(+a)` demanded by a node of
`q(+a)` demanded by a node of `p(+a)` keeps both alive after the root
unregisters, like the records above. But a lingering dead slice is correct
data wasting memory, so the fix is an ordinary tracing GC: mark from the
registered roots along demand edges, sweep the rest, at leisure. A record
zombie by contrast is wrong data with a valid certificate and must be
resolved within the commit; hence DRed there, and GC here.

### Pull as a work queue, parallelism (settled)

The pull "stack" is the sequential picture; implement pull as a **work
queue** from the start, even single-threaded. Pull discovers the same
DAG push walks, top-down, with the joins explicit in the structure and
no height scheduler.

- Sources of independent work: roots pulled at commit; the dirty
  upstream slices of one slice (fork, join); the stale nodes of one
  bucket (distinct subtrees; buckets join in step order).
- A slice in progress carries a completion future; a second puller
  parks on it instead of recomputing (memoize-with-futures).
- **Leaf batching needs the queue even single-threaded.** A node that
  needs a leaf record parks itself (its env is stored, so it is resumable
  by construction); the scheduler runs whatever else is runnable; the
  leaf batch is flushed when nothing else can proceed: one query per
  leaf relation per round instead of one per node. Plain recursive
  pull would block on the first leaf demand.
- Python: threads give I/O concurrency for leaf fetches, no CPU
  parallelism under the GIL; free-threaded builds change that later. §8
  requires no determinism of evaluation order, so semantics do not
  stand in the way.
- What gets harder: the negative-cycle check walks the wait-for graph
  instead of a stack, and a positive cycle across tasks would deadlock
  without detection, so the SCC fixpoint is driven by the scheduler, not
  by recursion (as in Salsa).
- v0: single-threaded task queue with leaf batching; futures and the
  wait-for graph kept in the data model so threads can be added without
  changing the shape.

### Re-derivation instead of nodes (dismissed for v0)

Re-derive-to-retract would need subscriptions addressable by value (the
full env at a plan step identifies the logical node, up to duplicates from
ignored positions, resolved by counting), reconstruction of old state from
version chains, and determinism. A pure-count variant avoids per-node
storage but loses notification routing (coarse re-run of whole rule
instances). Nodes are the v0 choice.

### Non-incremental slices (settled as a knob)

Incrementality can be refused per relation or per rule where things
rarely change, trading recompute time for memory. Recompute-and-diff is
a legal implementation of revalidation for any slice, so the knob
changes what a slice *stores*, not how the rest of the engine sees it.

- **Kept**: the records dict (for serving and for the diff), the
  certificate, the version chain, and one **dirtiness subscription per
  input slice**: an entry in the producer's `subscribers` that
  represents the whole consuming slice instead of a node and carries no
  observed version; it only needs to know that *something* changed.
- **Dropped**: the whole derivation tree: nodes, `args`, `observed`,
  `children`, dup lists. That is most of a slice's memory.
- **On revalidation**: re-run the rule for the slice from scratch, diff
  old records against new, publish the net delta. Incremental consumers
  depend on it without noticing; it is a full citizen of the delta
  graph.
- **Trade**: the classic materialized-view one. Incremental costs memory
  proportional to nodes; recompute costs time proportional to slice size
  per change. Reference data (country tables, price lists,
  configuration) is big and rarely changes: recompute wins. Per-object
  working-set slices are small and change often: incremental wins.
  Leaves are on the recompute side by nature.
- **Constraints**: not for relations in a static recursive SCC (no nodes
  means no justifiers; the grounding argument rests on them). A
  slice-level choice, so it composes with epochs (aliases like any
  other) and with the witness knob and segment splitting, which are the
  same decision at finer grain. Explicit knob first; automatic choice by
  change frequency versus size is the cost-based version, to be decided
  after the benchmark harness shows numbers.
- **Not this**: a slice storing no records at all, recomputed on every
  read. It has nothing to diff against, cannot publish deltas, and its
  consumers would have to recompute-and-diff too, so non-incrementality
  spreads downstream. Only for cheap, rarely read slices, later.
- **Linear rules are the same either way.** A generator-free rule mode
  is one segment and one node per rule instance; revalidating it already
  re-runs the whole segment from `args` and diffs the head contribution,
  which is what the non-incremental version does with records. Same
  work per change, same input slices. The knob matters only where there
  are generators, since the derivation tree (one node per input record
  per level) is the memory.

**The memoized-function view.** A keyed slice of a generator-free rule
is a memoized computation keyed by its bound values, tracking the slices
it read as dependencies, marked dirty when any of them changes,
recomputed on next read, notifying its readers only if its value
changed: a Solid.js/MobX computed or a Salsa query, with the record as
the memo and the dirtiness walk plus pull as the scheduler. What the
relational layer adds is what a signal library lacks: the key is a tuple
with modes rather than one closure, so one rule yields a family of memos
on demand; generators turn a computed into a set with per-element
incrementality instead of a value recomputed whole; leaves are ORM
records with the database doing the selection. Linear rules are the
degenerate case where all of that collapses to the signal model, which
is a consistency check on the model.

### Storage strategy

v0: one dict per slice. Later, optional **record-group storage** per key
prefix: one dict `T -> slots object` shared by all `+T` slices under the
prefix (one slot per relation, sentinel for absent), regardless of which
rules fill which slot; certificates, versions and `subscribers` stay per
slice. Nothing semantic changes; it only saves memory on wide leaves.

---

## 9. Definition errors and live redefinition (settled)

- Every head (and mapping) contributing to a relation must agree on the
  position profile, the FD contract, and the fold policy. Disagreement is
  a definition error naming both heads. `== sum(X)` in one head and
  `== bag(X)` in another is an error; so is `== sum(X)` next to a plain
  `== X`.
- In live loading, the relation's contract is what its currently loaded
  heads agree on; an incoming head that disagrees is rejected as a
  rule-level error and consumers carry on unchanged. Changing a contract
  means changing all heads; within one module that is atomic on reload;
  across modules there is a window of errors, and the message names the
  conflicting loaded heads.
- A call site's meaning is fixed by its own text plus the contract the
  engine checks against the current declaration. A redefinition that
  breaks what a site asserted fails loudly; nothing adapts silently.

Redefinition scenarios for `order.profile`:

| change                          | `== v.C` sites     | `(v.C)` sites     |
|---------------------------------|--------------------|-------------------|
| key ≤1 becomes FD position      | keep working       | keep working      |
| FD position becomes key ≤1      | keep working       | keep working      |
| FD position becomes key, no ≤1  | FD assertion error | works, may yield  |
|                                 |                    | more records         |
| key ≤1 becomes key generator    | FD assertion error | works, may yield  |
|                                 |                    | more records         |

The only silent change is the one a `(v.C)` site opted into by asserting
nothing. Key-versus-FD affects modes, not sites: after a change, any site
using a reverse mode is served or errors per §6 in either spelling.

- Cross-rule agreement is checked via demand (definition error surfaces
  when the slice is demanded or revalidated).
- Static lint: generator variables dropped from a head (bag-vs-set
  confusion).

---

## 10. Undefined relations (settled)

An undefined relation is one with no rules, no facts, no mapping and no
fact source. Defined-but-empty (a mapping, a fact store, a rule with no
instances) is different and legal.

- Static: a gutter warning at the relation application, "no rules, facts,
  mapping or fact source define `order.fulfillment_delayed/2`", listing
  defined relations with the same names and a different position profile
  ("did you mean `order(O).fulfillment_delayed`, a set of orders?"). Only
  a warning at load time, since definition order does not matter in a live
  system.
- Runtime: demanding an undefined relation is an **error**, not an empty
  result.

---

## 11. Python-side access (settled earlier, brief)

- Interactive/imperative access goes through a **facade**: an interned
  object holding (signature prefix, key) that looks up relations named
  `prefix.<attr>`. This naming convention lives in the facade only; the
  engine knows nothing about it. `order.fulfillment_delayed` on a facade
  may return a bool from a membership probe.
- Actions are opaque Python. (An older list of action combinators was
  dropped; whether actions get combinators at all is open, §14.)
- Transaction facts instead of `utcnow()`.
- Multi-wave updates with a flush per wave (see "Waves and epochs").

### Waves and epochs (settled)

The wave model: `S1 -> ml1 -> S2 -> ml2 -> S3 ...`. Each **mutation
list** `ml_k` is computed by special relations named in top-level Python
setup code and applied at the ORM level (mutation lists concern mapped
instances only, never arbitrary objects). The chain may reach a fixpoint
(`ml_k` empty); loop details are deferred. Two kinds of change must be
handled without rolling the world back to `S0` and replaying:

- a **wave-0 data change**: "as if this attribute had this value in the
  DB", on any mapped instance;
- a **rule change**, which can affect several waves at once.

Rejected: per-epoch snapshots of every slice (persistent tries, cheap
copying with ownership marks). Structural sharing would solve the record
memory, but each epoch would still have its own nodes and
subscriptions, so a wave-0 edit would be walked once per epoch, and two
epochs applying the same delta to a shared trie both copy the path, so
the sharing erodes to full copies over time. Sharing records is not sharing
the derivation work.

**Settled: the epoch is a coordinate of slice identity, implicit in the
syntax, and slices alias across epochs until touched.**

- The state at epoch `k` is not a copy of the database. The leaf
  relations at epoch `k+1` are "epoch `k` unless `ml_k` says otherwise",
  where `ml_k` is the mutation-list fold at epoch `k` (below). Rules
  never mention epochs (implicit) except the one epoch relation (below),
  which also keeps users from reading across epochs and keeps the chain
  a chain. The overlay is the engine's, never hand-written, so that the
  simulated chain and the real run (apply `ml_k` to the ORM, re-read the
  leaves) agree by construction; this requires the mutation list to be
  the only writer.
- **Leaf slices at epoch `k+1` are overlays**: the epoch-`k` slice plus
  the keys `ml_k` touches. An overlay with no overridden keys *is* the
  epoch-`k` slice object.
- **Derived slices alias.** When `X` at epoch `k+1` is demanded, its
  inputs at `k+1` are demanded first; if every one of them is the same
  object as at epoch `k`, `X@k+1` is declared an **alias** of `X@k`: no
  records, no nodes, one pointer, reads forwarded. A slice therefore has
  one more state besides clean / dirty / in progress / erroneous:
  *alias of*.
- **What does not break an alias**: a delta flowing into `X@k`. `X@k+1`
  has no subscriptions; a reader at `k+1` reads the already revalidated
  `X@k`. A wave-0 edit to an order no mutation list touches is
  revalidated exactly once, at epoch 0, and every later epoch forwards.
- **What breaks an alias**: an input **materializing**, i.e. some slice
  `X@k+1` reads stops being the same object as its epoch-`k` twin, which
  happens only when `ml_k` touches keys of that leaf slice. Precise to
  the slice: `ml_k` setting `order(o).state` materializes
  `order(+o).state@k+1` but not `order(+o).ticket@k+1`, so
  `order(+o).ticket(-)@k+1` keeps its alias. An alias holds one cheap
  subscription, "tell me if any of my inputs materializes at `k+1`";
  dissolution is an event.
- **On dissolution**, v0 **recomputes** `X@k+1` from its epoch-`k+1`
  inputs (cold evaluation of one slice: for a 5,000-node slice
  roughly 25 ms of Python, paid once per touched slice per epoch). After
  that `X@k+1` is an ordinary slice with its own records, nodes and
  version chain, and later wave-0 edits reach it as deltas through its
  own subscriptions. Cloning `X@k`'s records and node tree, re-pointing
  subscriptions and applying the override set as a delta is a possible
  later optimization behind the same interface.
- **Cost model.** Memory is the sum over epochs of the slices that
  epoch's mutations actually reach, not epochs times slices. A wave-0
  edit costs one revalidation per epoch where the affected slice is
  materialized. A rule change dirties that relation's materialized
  slices at every epoch (aliases have nothing to dirty), each
  revalidating incrementally against its own inputs; "affects several
  waves" is just "has slices at several epochs".
- Known coarse spot: aliasing is all-or-nothing per slice, so the first
  mutation touching a large (unbound) slice pays a full recompute for a
  one-record difference. Unbound slices over large relations are the slow
  case of this engine everywhere (per-record materialization, hub fan-out,
  joins in Python instead of SQL), and the planner's preference for
  keyed modes plus the combined form are what keep them rare.

#### Mutation list fold and the epoch relation (settled)

The engine never gains rules at runtime and never edits itself. It gains
one fold type and one reader of that fold's output (the overlay). All
the rest is user rules producing values.

- **A mutation is a plain value**, `Mutate(instance, attr, new_value)`,
  immutable and hashable, computed by ordinary rules like any string or
  int, deduplicated by set semantics like any record. Nothing special
  about it. Mutations concern mapped instances only.
- **`mutlist` is a fold** with engine support, in the family of `sum`
  and `setof`. Its combining function groups contributions by
  `(instance, attr)` and applies `same` semantics within a group: two
  contributions for one key with different values are a fold error, and
  since contributions come from nodes the error names the rule instances
  that disagree. Conflicts are definition errors at the wave, with both
  rules named, never last-writer-wins; order inside a wave does not
  exist (the list is a set). Incrementality is ordinary fold
  incrementality: contributions are added and retracted as nodes come
  and go, a changed group is a delta on exactly the leaf slices of that
  key at the next epoch.
- **The overlay reads the fold.** The leaf slice for `(o, state)` at
  epoch `k+1` asks `mutlist(k)` for its group and gets the value or
  nothing; the fold's own grouping dict is the index.
- **The epoch relation is the one place the epoch is explicit**:
  `r.epoch(v.N).mutlist == mutlist(v.Mut)` (spelling of the fold call
  open). The engine's contract: the *body* of a rule for
  `epoch(v.N).mutlist` runs against the epoch-`N` state, its *head* is
  keyed by `N`. Everything else reads its epoch implicitly. Several
  rules may define it, conditioned on `N` or on derived phase data
  (`epoch(v.N).phase == "allocate"`), which gives staged pipelines and
  "repeat until stable" loops with no control flow at all.
- **The chain is demand.** Nothing drives the loop. The root goal "final
  state" demands `epoch(N).mutlist`, which demands the epoch-`N` state,
  which demands `mutlist(N-1)`, down to the DB. `epoch(N+1)` exists iff
  `mutlist(N)` is non-empty; final is the first `N` where it is empty.
  Recursion in `N`, strictly increasing, so no slice cycles. Only epochs
  a root needs are computed. The wave cap (§8) bounds non-termination
  (ping-pong mutations) with an error naming the offending mutations.
- **Effects.** Non-data side effects (emails, API calls) must not run
  during simulation. They are modeled the same way, `epoch(v.N).effects`
  as a fold of plain effect values, executed once at the real run after
  the chain settles. Opaque Python actions are confined to that edge.
  Without this distinction someone sends an email from a rule and the
  model breaks.
- **Leaves per key.** Untouched attributes, the vast majority, need no
  structure: the epoch-0 leaf slice serves every epoch by aliasing. A
  leaf key ever touched by a mutation gets a small sorted list of
  `(epoch, slice)`; resolving it at epoch `k` is "largest epoch ≤ k",
  a key with no list resolves to the base slice. The wave-0 override is
  an entry at epoch 0 in the same list, the base being the value on the
  mapped instance. The mapped instance holds one value, the session's;
  simulation never writes to it. Applying the final lists for real
  happens at commit, when the chain collapses into the database and the
  epoch structures are discarded; the next session starts from epoch 0
  equal to the DB.
- **Assessment.** This is the synchronous-reactive discipline (Dedalus
  "next", Bloom deferred operators, Esterel, event sourcing with
  rule-generated events): each wave a pure function of a state, mutation
  as data, nothing computed in a wave visible in that wave. Gains:
  conflicts as errors, no order inside a wave, an inspectable run (states
  with explicit mutation lists between them), what-if for free (wave-0
  overrides). Costs: multi-wave thinking ("allocate an id, then use it"
  spans two waves), possible non-termination (capped), the effects
  distinction. Immediate-visibility reactivity gives glitches and order
  dependence, transactions give atomic batches without derivation,
  event sourcing gives the log but nothing computes the events; this
  keeps the guarantees of all three.

#### Driving code: the link chain, flush and commit (settled)

The top-level protocol of a run (a request, a session step):

1. The driving code gives the engine a **chain (graph) of links**. Each
   link is a goal the engine runs at the current epoch and that returns
   a mutation list via `== v.mut_list`. Each link points to the next;
   a link may point back to an earlier link or to itself: a fixpoint
   loop. The chain is **data the engine holds**, a small graph object
   (links, `next`, back edges, caps), not a Python loop the engine
   cannot see: the engine runs it, records which link produced which
   epoch, can show the run (epoch, link, mutation list) for inspection,
   and re-runs the same graph incrementally after a wave-0 override or a
   rule change. The schedule is the only genuinely imperative part and
   is the only part the driver writes.
2. The engine crunches on the chain until done. **Loop termination**: a
   self-loop is done when its wave returns an empty mutation list; a
   cycle of several links (`A -> B -> A`) is done when a **full round**
   of the cycle produced no mutation, since an empty `A` followed by a
   non-empty `B` can change `A`'s inputs. A cap on rounds per cycle,
   with an error naming the mutations still flapping, guards
   non-termination.
3. The result is the **mutation registry**: all mutations accumulated
   across the waves. What is applied is the **net** effect, the last
   value per `(instance, attr)`, i.e. final state minus `S0`. The
   per-epoch lists are kept too: they explain why each final value is
   what it is and are the blame source for flush errors.
4. With the leaves in their end-wave state the engine may be **queried
   for anything else**: root goals demanded at the final epoch, e.g. a
   `response == v.Json` goal or a serialization; the sending is an
   effect like any other.
5. The driving code **applies the registry to the mapped instances,
   flushes, commits, and only then runs the effects** (emails, client
   responses, API calls). Effects must never run for a transaction that
   did not happen: the outbox discipline.
6. **Flush errors** have a clean story: the mapped instances are rolled
   back; the engine state is untouched because the chain was a
   simulation; a constraint violation is mapped back through the
   registry to the epoch and rule that produced the offending mutation;
   the user fixes the rule or the data and re-runs, incrementally.

Possible refinements of the link graph (ideas, not yet settled):

- **Back-edge pointers.** Only the link carrying a cycle's back edge
  needs two pointers: `repeat` (the cycle's first link) and `exit` (what
  follows once a round produced nothing); the other links of the cycle
  have just `next`. The "did this round produce mutations" check is made
  at the back-edge link over the epochs since the cycle's first link.
  Nested cycles compose, each with its own back-edge link and round cap.
- **Validation links, not a second node kind.** A link is a goal that
  returns a fold value, and the *type of that value* decides what the
  engine does: a mutation list is applied as the next epoch's overlay
  and the chain advances; an **error list** (a fold of plain error
  values carrying blame: rule, instance, message) advances if empty and
  otherwise **halts the chain** with the errors as the run's result, no
  commit. Placements are usage patterns of the same construct: at the
  start, input validation of the wave-0 data so a bad request never
  computes mutations; at the end, invariant validation of the final
  state, richer than DB constraints and with blame; between phases when
  a phase has preconditions. Validations are relations over the state,
  incrementally maintained like everything else, so a re-run after a fix
  costs only what changed. Errors being plain values, a rule may also
  consume them (an invalid order gets a mutation) with no special
  support; only the halting of a validation *link* is engine behaviour.

#### Live tests (idea, follows from root goals)

A test is a relation whose records are failures,
`test.refund_after_cancel.failures == setof(...)`, over fixture data
given as wave-0 overrides on a shared base. Registered as a root, it
stays evaluated; no new engine mechanism is involved, a test root is a
root.

- **Precise test impact for free.** A rule edit dirties exactly the
  slices depending on it, so exactly the tests whose derivations pass
  through that rule re-run, incrementally, and only the affected parts:
  "tests whose data flow touches this rule", not "files importing the
  module". What test-impact tools approximate with coverage maps, taken
  from the dependency graph itself.
- **Failures carry blame.** A failure record is a derived record; "why"
  walks its nodes: rule instance, inputs, epoch.
- **Chains are testable without a DB write.** A test runs the link chain
  in simulation and asserts on the registry or the final-epoch state;
  nothing is flushed, effects never fire. Fixtures shared between tests
  alias across their epoch chains: a hundred tests over one base dataset
  do not hold a hundred copies.
- **Tests as a gutter.** Pass/fail per test rule updates as you type:
  live development extended to correctness, not only values.
- **Knobs are scheduling, not semantics**: which roots are registered
  (all tests, the current file's, a tag), when they are pulled (every
  commit, on save, on demand), how much memory live tests may pin (the
  sweep treats unregistered tests as cache).
- Bridge to build early: a `pytest` adapter that registers a root goal
  and asserts it is empty, so tests live in an ordinary suite and are
  also live in a session.

Open (§14): **leaf coherence across transactions**. After commit the
epoch-0 slices the registry wrote are known, but records changed by
other transactions or processes are not, and a request-scoped ORM
session does not know either. Safe v0: invalidate epoch-0 leaf slices at
transaction boundaries, which throws away the derived cache between
requests; anything better needs a DB-side change signal or a versioning
scheme. This decides whether the engine is a per-request computation or
a long-lived cache.

### Host process, tooling and REPL (settled in outline)

The system wants to be Smalltalk, with one difference in our favour:
**the image is a cache.** Everything the host holds is derived from the
database plus the rule files, so it can be killed and restarted at any
time and rebuilds lazily. No image file, no image-versus-source drift.

**Host.** One long-running process: engine, ORM session, file watcher,
live loader. The host **is the application process** (e.g. the Flask
process); the interactive services are an optional extension installed
only in development (like Werkzeug's debugger), so production runs the
same code with the extension absent: one process type, one `Engine`
object embedded in the app.

- **One engine thread.** The engine is single-threaded by design; it
  gets its own thread with the task queue as inbox. A request handler
  submits "run this chain, give me the result" and blocks on the
  future; LSP, debug adapter, inspector and REPL are further clients of
  the same queue. Nothing touches slices from a request thread. Several
  gunicorn workers each have their own engine and cache (leaf coherence
  is then per worker).
- **Two reloaders do not mix.** The framework's process-restarting
  reloader is disabled in host mode; DyRel's watcher reloads: rule
  modules through live loading with state kept (re-execute the module,
  diff its rule set against the previous one, feed the differences to
  live loading; opaque actions re-resolved by name), other modules by
  module reload where safe, process restart for the rest (mapping
  changes). Restart is cheap because the image is a cache, but it is
  the exception.
- **Control channel**: request/response over a socket (JSON-RPC or
  similar), serialized snapshots, never remote object proxies. `rpyc` is
  not needed: proxies to live objects would evaluate on the wrong
  thread, hold the GIL across the wire and leak identity semantics.

**No per-editor plugins.** Three editor-independent surfaces:

- **LSP server**, a thin separate process over the control channel
  (dies with the editor, host runs headless). Carries what an editor can
  show: diagnostics as the gutter (undefined relations, definition
  errors, mode errors, stratification lint, failing tests; the host
  produces them with source positions on live load, the server forwards
  per file), hover (value of the relation under the cursor for a chosen
  key), code lenses (test status, record counts), inlay hints (inferred
  modes, ≤1), go-to-definition (relation to its rules), find-references
  (consumers). `pygls`; diagnostics in ~100 lines, each feature one
  handler. Runs **side by side with the Python LSP server** (`ty`):
  clients attach several servers per file type and merge results tagged
  by source. The DyRel server never answers Python questions. A `.pyi`
  stub giving the `v`/`r` namespaces a `__getattr__` keeps the type
  checker quiet and makes the objects typed. Sublime/Neovim: a config
  entry; VS Code: a minimal launcher extension; PyCharm: its LSP API,
  reduced feature set.
- **Debug adapter (DAP)** for derivation inspection, where LSP is the
  wrong shape: a stack frame per node on the path from the rule
  instance root to the record, with the plan step's source position;
  variables = the node's `args` by `step.varnames`, input records
  expandable; step in/out = child/parent node; threads = roots or
  epochs; a breakpoint on a rule line = "stop when this rule instance
  derives or retracts" (honoured at the contribution site); evaluate =
  a query at the node's env. Sublime Debugger, nvim-dap, VS Code;
  PyCharm stays on the inspector.
- **Web inspector** served by the host for tables and graphs: relations,
  slices, records, why-chains as trees, epochs and mutation lists side
  by side, test results. Bridge from the editor: an LSP code lens or
  command that opens the inspector at the record's URL. An
  editor-specific plugin is only ever an optional convenience.

**REPL.**

- **Evaluator on the engine thread**: a persistent namespace per REPL
  session prepopulated with `r`, `v`, the engine, the ORM session. Each
  submission is `compile(src, "<repl>", "single")` (bare expressions
  print), executed via the task queue on the engine thread, stdout and
  stderr captured, result serialized. The **displayhook** carries the
  DyRel behaviour: a goal as result is run as a query and rendered as a
  table, a facade prints its value, a slice its records, an exception
  prints with the generated-line-to-goal map applied. `r += ...` at the
  REPL registers into a `<repl>` module that live loading treats like
  any other: define and redefine rules interactively, definition errors
  inline. The same evaluator serves the debug adapter's evaluate and
  the inspector's query box.
- **Client**: `dyrel repl` on `prompt_toolkit`; `codeop.compile_command`
  locally to detect complete input; source over the control channel;
  completion from the session namespace plus relation signatures and
  segment names.
- **Jupyter, second**: a wrapper kernel (`ipykernel.kernelbase.Kernel`
  subclass, `do_execute` forwarding to the host, ~100 lines) gives
  notebooks and rich consoles in VS Code, PyCharm, Neovim; tables as
  HTML.
- Not this: `code.InteractiveConsole` on a socket thread, or `rpyc`
  classic mode: wrong thread, no goal context, no displayhook.

CLI shape: `dyrel host`, `dyrel repl`, `dyrel lsp`, `dyrel dap`,
`dyrel test`, `dyrel query '<goal>'`.

---

## 12. Worked examples

`fib` is a good **syntax** example (mode `+N` only, plain fold, memoized
instances) and a bad **use case** (nothing mutable underneath; demand
support GCs one-off query chains; a live root retains the chain
pointlessly). A later static "pure relation ⇒ plain tabled mode" may
exist. Documentation should motivate with an ORM-backed example.

```python
r += (r.fib(0).value == 0)
r += (r.fib(1).value == 1)
r += (r.fib(v.N).value == v.Result) <= (
    v.N > 1,
    v.N - 1 == v.N1,
    v.N - 2 == v.N2,
    r.fib(v.N1).value == v.A,
    r.fib(v.N2).value == v.B,
    v.A + v.B == v.Result,
)
```

```python
# head: key Order, FD position subtotal
r += (r.order(v.Order).subtotal == v.Amount) <= (...)
# body read, asserting the FD
r.order(v.Order).subtotal == v.Amount
# body read, asserting nothing
r.order(v.Order).subtotal(v.Amount)
# two keys, one FD position
r += (r.product(v.Prod).at(v.Date).costs == v.Price) <= (...)
r.product(v.Prod).at(v.Date).costs == v.Cost                  # body
# value struct in the FD position, built in the body
r += (r.route(v.Rt).endpoints == v.E) <= (
    ...,
    v.E == Endpoints(from_=v.F, to_=v.T),
)
```

```python
r += (r.city(v.C).country(v.X)) <= (
    r.city(v.C).region(v.R),
    r.region(v.R).country == v.X,
)
```

Three sentences for users: every segment with an argument is a key
position; a bare trailing segment filled with `== X` is the value; any
other bare segment is only a name.

---

## 13. Earlier decisions still standing (from prior sessions, less detail)

- Modes, not adornments.
- Lazy invalidation with version chains; consumers revalidate on demand.
- One signature, one relation (identity per §3).
- Need sets per plan step; conglomeration of leaf subgoals; greedy join
  planning; ruff-compatible formatting of rule code.
- Actions opaque; transaction facts; multi-wave updates with flush per
  wave (see §11).

---

## 14. Open items

- Zero-key relations with an FD position (constants with a value).
- Objects with identity: a handle standing for the relations under a
  prefix with a fixed key (the facade of §11 as a value), families of
  handles declared over prefixes (`o.Name += r.order(v.O).insurance`),
  and late-bound reads through a handle (`r[v.I].net`). Discussed at
  length. Attribute-level reactivity needs none of it (keyed slices
  already give it); the handle is only needed to pass "the group" around
  without naming its prefix. A late-bound goal with free positions
  cannot be placed by the planner without knowing the relation, so any
  version needs a declared family or per-prefix planning at first
  demand. Deferred; value structs (§3) are the v0 answer to compound
  data.
- Whether a value-struct construction may appear inline on the RHS of
  `sig ==` instead of via a separate expression goal.
- Whether `unique(...)` declarations return as an escape hatch beyond the
  head `==`.
- Record-group storage strategy (later).
- Mode assertions for eager planning at load time (§6, later).
- Mercury-style determinism declarations, user cost hints (later).
- Whole-subtree replay knob per rule/generator (later).
- Whether actions (Python side, §11) get combinators at all.
- Packed `ts`/`head` storage per slice (with record-group storage, §8).
- Leaf coherence across transactions (§11, driving code): invalidate
  epoch-0 leaf slices at transaction boundaries in v0, or a DB-side
  change signal / versioning scheme later.
- The team-facing design document itself.

---

## 15. Vocabulary map from older documents

| older term (`readme.full.md`, earlier notes) | this file |
|---|---|
| projection | slice |
| predicate | relation |
| adornment | mode |
| atom (body) | subgoal / relation application |
| `p(K...) -> V`, `>>`, `out(...)` | `sig == V` / keyword form |
| `v == V` marker on any position | `sig == V`, trailing bare segment only |
| anonymous trailing position (`fib(N) == R`) | removed; `fib(N).value == R` |
| composite record (several FD positions) | multi-value head or value struct |
| identity cell, trie store | rejected; facade + per-slice storage |
| Rete/TREAT network, witness GC | superseded by nodes (§8) |
| row | record |
| record (earlier in this file) | node / derivation node / join node |
