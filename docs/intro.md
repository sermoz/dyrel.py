## What?

*DyRel* (for *Dynamic Relations*) is a Python-embedded relational engine featuring
incremental evaluation, reactivity, SQL integration, and first-class support for live
interactive development. It is based on the
[Datalog](https://en.wikipedia.org/wiki/Datalog) language.

DyRel can also be regarded as a deductive in-memory database. A deductive database has
some basic data (called *facts*) and also *rules* of deducing new data from existing ones.
All the information is represented with relations -- same as in normal _relational
databases_ such as MySQL or PostgreSQL, where relations are just usually called _tables_
-- but some of these relations can be specified with rules, not just pure data, and
evaluated lazily (on demand). Should anything change in the source data, the deduced one
is recomputed incrementally, i.e. only the affected portion of the rule-based relation is
re-derived.

DyRel is designed to be a "business logic engine" for Python applications. It should be
able to handle most of the rules and logic of the domain model, leaving pure Python to do
the high-level orchestration and glue different subsystems together.


## Why?

The project is expected to solve the following major issues with the current state of
DB-backed application development in Python (although most of the points below are true
for other languages, too):


### Poor interactive experience

Despite Python being a dynamic language that encourages fast development and a tight
feedback loop, the current state of the art is far from what it could be. Developers have
to rerun tests, reload pages, restart dev servers, relaunch scripts, etc. to see the
effect of their changes in the code. Meanwhile, reliance on static analysis tools
continues to grow. But static analysis tools can infer or check only so much for you in a
dynamic language like Python, no matter how smart and sophisticated they are. Hence the
trend to make Python more static with type hints and other extensions, as developers want
the code to be more amenable to static inspection.

DyRel claims to substantially improve programming experience by making it much more
interactive and responsive. Being a deductive database, it reacts to every change in rules
or facts immediately, upon a source file save. The so-called *root queries* are always
incrementally maintained in an up-to-date state, on any change. Analogously, the top-level
*effects* are rerun if anything they depend on is changed.

**FUTURE NOTE** the system should have ways to suspend automatic data maintaining. We
don't necessarily want major things to happen on individual file save.


### Imperative idiom is bad at relations

The vast majority of what we do is managing relations between domain entities: all kinds
of CRUD (Create/Read/Update/Delete) operations, and then filtering, sorting, validating,
etc. Often these entities can be accessed or searched from multiple ends.

For example, if you have orders, vouchers and customers, you may also have these relations
between them:

- multiple vouchers can be used to buy a single order;
- an order is always made by a single customer.

Even in a simple example like this, you already have quite a few ways to interact with the
data. For instance, you can ask:

- whether a given customer used this particular voucher?
- who used a given voucher, and on which order?
- what are all the vouchers that a given customer used during the last month?
- what vouchers were used for this order?
- etc.

In all of these usages, the basic setup is the same. What differs is the side from which
we're entering it. Whether we start from the voucher, order or customer, or just by
searching in a timespan, in any case the core relations between the entities are the same.
Yet, this *permanency of relations is not expressed anywhere in the code* in a
conventional language in which business logic is typically implemented: for any access
pattern to the data, we need to make separate functions/classes/interfaces.

However, *the permanency of relations is preserved at the DB level*. An RDBMS like
MySQL or PostgreSQL has just one definition for tables (relations), and we can query
them however we like -- the database will figure out how to access the data.

So with this context laid out, what DyRel is trying in a way to do is *extend the database
to the application programming layer*. In your application code, you should still have
some definitions of entities and relations between them, and the system should be able to
figure out how to go about them.


### *SELECT \** antipattern and the *N + 1* problem

The *SELECT \** antipattern refers to the fact that most ORMs emit `SELECT * FROM
customer` when you call `order.customer`. And the *N + 1* problem means that this code:

```py
for order in orders:
    use_customer(order.customer)
```

.. will emit a separate `SELECT * FROM customer WHERE order_id = :order_id` for each
`order` from `orders`.

Of course, there are ways to remedy both of these problems. For example, in
[SQLALchemy](https://docs.sqlalchemy.org/en/20/) we may want to do something like this:

```py
from sqlalchemy import select
from sqlalchemy.orm import joinedload

stmt = (
    select(Order)
    .options(
        # Load the customer relationship, but ONLY fetch the id and name columns
        joinedload(Order.customer).load_only(Customer.id, Customer.name)
    )
)

orders = session.scalars(stmt).all()

for order in orders:
    use_customer(order.customer)
```

That does solve the immediate problem, but now we got another one: how to know in advance
which of the columns we're gonna need later? That's not an issue if we explicitly run the
queries and only select what we need each time (see [sqlc](https://sqlc.dev/)), but that
would not be an ORM anymore.

If we're using an ORM library, we think about an *order* as a row in the `orders` table in
the database, so we naturally expect that all the columns of that table are available as
`order`'s attributes (e.g. `order.total_amount`). But now with deferred loading of columns
and relations, it's not that simple anymore: when you write `order.total_amount`, the
`.total_amount` should better be already pre-loaded, or otherwise you again get the same
*N + 1* problem, only this time even worse: it is now a *N \* M* problem, where *M* is the
number of columns that were not pre-loaded.

Conversely, when you are pre-loading stuff, you should be able to "guess the future". Not
only this creates implicit dependencies between different parts of the codebase (i.e.
changed this function => be sure to update the eager-loading code in a distant module to
include a new column/relation), it also breaks the usual abstraction guarantees that
programmers normally expect:

```python
from sqlalchemy import Select, select

def load_vouchers_by_code(code: str) -> Select:
    select(Voucher).where(Voucher.code.contains(code)).options(
        # What should be eager-loaded here???
    )

```

In this example, the `load_vouchers_by_code()` cannot be thought of as a function that
loads vouchers by code anymore. Because it also has to know what columns and relations on
a Voucher it needs to load. Consequently, it's no longer possible to use it from multiple
places, since two distinct usages of vouchers will surely need different sets of columns
and relations loaded. So we need to make these "eager-loading options" part of the
function's parameter list, but then how much of ORM is there left? If the client code
needs to pass explicitly what it needs to load on a Voucher, this is already not much
different from something like *[sqlc](https://sqlc.dev/)* indeed, where we build our data
structures around queries and not tables. It's already more of a query builder rather than
an ORM.


#### DyRel approach

DyRel attempts to solve both of these problems in a unique way: as the default and basic
case, only 1 column for 1 instance is loaded with a separate `SELECT` query. Then, these
queries can *conglomerate* (be *merged*) in 2 dimensions:

- *vertical*: load the column for multiple instances with 1 query, by changing the `WHERE
  pk = :val` condition in the query to `WHERE pk IN (:val, :val, ...)`. This is possible
  because being an embedded engine, DyRel can suspend evaluation at any place. So when we
  need to load a mapped attribute (column) on an instance where it's not yet loaded, we
  stop here and proceed with other work that the engine has queued. Then, when nothing
  except emitting SQL is left, we see how to load stuff for all the instances with as few
  queries as possible;

- *horizontal*: load multiple columns for a single instance, just by appending all the
  needed columns to the `SELECT` list of columns. This happens due to explicitly combining
  of goals by the programmer. (See down below for details.)

In a typical use case without any explicit tweaking on the programmer's behalf, DyRel is
expected to automatically provide the equivalent of the SQLAlchemy
[`selectinload`](https://docs.sqlalchemy.org/en/21/orm/queryguide/relationships.html#sqlalchemy.orm.selectinload)
with only needed columns loading (not `SELECT *`).


**FUTURE NOTE** there are some clever techniques for improving the horizontal
conglomeration of queries due to the fact that DyRel is introspective and can understand
its own code, but this won't be implemented in the first versions of the engine.

**FUTURE NOTE** the best thing that DyRel will be able to do without manually specifying
any loading options is `M` queries, where `M` the number of tables involved, independently
of `N` -- the number of loaded instances. And this would be an ideal case. In a common
case in practice the real number of queries will be something closer to `2*M` or `3*M`.
This fact reflects the fundamental trade-off inherent to the concept of Object-Relational
Mapping: we trade performance for convience of programming.


### Imperative updates and the "Spaghetti State"

In standard imperative programming, data mutations often lead to intricate, entangled
code. It becomes incredibly difficult to trace what is being changed, from where, and at
exactly what moment in time. When using a traditional ORM, this "entangledness" sprawls
out beyond the application's memory and directly impacts the database and business domain
entities. Deeply nested function calls might unexpectedly trigger UPDATE or DELETE
statements, leading to unpredictable side effects, invisible performance hits, and
hard-to-debug race conditions.

DyRel offers a more systemic, functional, and strict approach to Data Manipulation
Language (DML) and state modifications:

- *Accumulation over Mutation*: Instead of assigning values directly to mapped attributes
  and triggering immediate changes, all intended changes are first accumulated in a
  *manipulation registry*. Nothing is mutated in place.

- *Reactivity and incrementality*: This registry is not just a static list; it is built
  incrementally and kept continuously up-to-date using the exact same reactive mechanics
  that power the rest of the DyRel engine.

- *Pre-execution Auditing*: Because the registry represents intended changes rather than
  executed changes, it can be thoroughly inspected, validated, audited, or logged before
  being applied (effectuated).

- *External Orchestration*: The driving orchestration code lives strictly outside of
  DyRel. High-level pure Python code runs DyRel to compute the registry, inspects it, and
  ultimately makes the decision to apply the changes.

Because the registry is reactive, applying a set of changes might trigger a new round of
evaluations. DyRel can compute this next wave of manipulations by incrementally reusing
the relations already built during the previous round. This enables highly complex
workflows, including the ability to run fixpoint loops until the domain state settles into
a valid final state.
