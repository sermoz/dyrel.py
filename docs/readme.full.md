# Basic usage

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


## Python DSL

Facts and rules are specified in dedicated Python modules:

```python
# File: rel/geography.py
from datetime import datetime
from dyrel import r, v


r += (
    r.order(2450).customer("Hans").total(5.50),
    r.order(2453).customer("Robert").total(10.40),
    r.order(2459).customer("Hans").total(7.20),
    r.order(2464).customer("Saskia").total(12.00),
    r.order(2465).customer("Julius").total(20.00),
    r.order(2472).customer("Saskia").total(8.00),
    r.order(2477).customer("Julis").total(4.00),
    r.order(2490).customer("Robert").total(16.40),
    r.order(2492).customer("Robert").total(3.00),
    r.order(2494).customer("Saskia").total(6.00),
)

r += (
    r.order(2450).created_on(date(2026, 7, 15)),
    r.order(2453).created_on(date(2026, 7, 15)),
    r.order(2459).created_on(date(2026, 7, 16)),
    r.order(2464).created_on(date(2026, 7, 16)),
    r.order(2465).created_on(date(2026, 7, 16)),
    r.order(2472).created_on(date(2026, 7, 17)),
    r.order(2477).created_on(date(2026, 7, 18)),
    r.order(2490).created_on(date(2026, 7, 19)),
    r.order(2492).created_on(date(2026, 7, 19)),
    r.order(2494).created_on(date(2026, 7, 21)),
)

r += r.customer(v.customer).made_order_on(v.date) <= (
    r.order(v.oid).customer(v.customer),
    r.order(v.oid).created_on(v.date),
)
```

All this "magic" is implemented, of course, with operator overloading, \_\_getattr__
and \_\_call__ special methods. Here's what this all means:

- `r.order().customer().total()`, `r.order().created_on()` and `r.customer().made_order_on()` are
  relations. Relations are designated with sequences of chained attributes.
- Relations `r.order().customer()` and `r.order()` are completely different relations. The
  fact that they share a common prefix is just a naming preference, otherwise they have
  nothing in common.
- `r` is a special object called the _relation root_.
- The `<=` operator (alluding to the leftward-pointing arrow) is used to specify _rules_.
  A rule consists of the _head_ and the _body_, and has this sense: if all the body
  expressions (*goals*) are true, then the head is also true. Rules provide a means to
  derive (deduce) new information.
- The `+=` operator for the `r` object means "add this rule or fact to the global
  database". What follows on the right-hand side is either a single fact, a rule or a
  tuple of either facts or rules. This grouping of facts/rules into tuples is purely
  stylistic. So this:

    ```py
    r += (
      r.order(2450).customer("Hans"),
      r.order(2453).customer("Robert"),
    )
    ```
  .. is completely equivalent to this:

    ```py
    r += r.order(2450).customer("Hans")
    r += r.order(2453).customer("Robert")
    ```
- `v` is a special object used to refer to variables through attribute access. Therefore,
  a variable name can be any valid Python identifier. Variables are interned, so we can
  `assert v.order_id is v.order_id`.

In relational programming, you think this: "when is this object together with this other
object and that third object satisfy this relation?". Of course, the number of "objects"
or values can be anything -- that's called the relation's *arity*. For instance, in our
example domain we can come up with these relations:

- `r.customer().placed_any_order_on()`: whether the given customer placed any order

 is that there are no input parameters and return value. A relation just brings together N values, and any one of them can be either in or out. When we have a *goal*, its N arguments may be *bound* or *unbound*


The rule body goals are very similar to JOINed tables in SQL. Each goal can have multiple
solutions, and they all are tried in turn. A rule application is essentially a depth-first
search for solutions, where each goal is tried sequentially, in the order they go in the
rule definition. The search tree is retained in memory and reused to achieve fine-grained
incrementality: if some new solutions appear for a particular goal in a certain node of
the search tree, we can continue right from that node with the newly found solutions.

There may be many rules for a single relation, and their results are all just merged
together without any deduplication.


## Source code reactivity

Given these definitions, we can query for information we need:

```python
# File: europe.py
import dyrel
from dyrel import r, v


def main():
    def city_added(sol):
        print(f"Got a European city: {sol.city}!")

    def city_removed(sol):
        print(f"Not a European city: {sol.city}!")

    query = dyrel.query(
        r.city(v.city).in_continent("Europe"),
        on_add=city_added, on_remove=city_removed
    )

    # `keep_updated()` makes sure that `query` is always kept up-to-date under any changes
    # to the relational information.
    dyrel.keep_updated(query)
    dyrel.watch_dir_forever("rel")


if __name__ == "__main__":
    main()
    sys.exit(0)
```

This program will print the 3 cities it can deduce are located in Europe:

```
Got a European city: Paris!
Got a European city: Toulouse!
Got a European city: Bordeaux!
```

If we then modify the DyRel module with our geography knowledge by adding London and UK
to the party, like this:

```python
# File: rel/geography.py

# Add the following facts:
r <<= (
    r.country("UK").in_continent("Europe"),
    r.city("London").in_country("UK"),
)
```

..and save the file, a new European city will be printed to the console:

```
Got a European city: London!
```

Now imagine that we lost the knowledge that France is located in Europe:

```python
# File: rel/geography.py

r <<= (
    ...
    # !!! Remove the following line:
    r.country("France").in_continent("Europe"),
    ...
)
```

Then all the French cities instantly stop to be located in Europe, too:

```
Not a European city: Bordeaux!
Not a European city: Toulouse!
Not a European city: Paris!
```

Of course, this happens because what was earlier derived now stops to be derivable: the
datum `r.country("France).in_continent("Europe")` is not provable anymore.

This dynamic incremental behavior is supported for any modification of the knowledge base,
including changes in the rules. Relational module is just re-parse and re-executed on
every modification. The system then compares the old rules and facts with the new ones,
and then applies only the differences, incrementally.


## Runtime reactivity

DyRel can not only react to relational source code changes -- it also supports normal
runtime reactivity. We just need to use some special *trackable* data structures for this:

```python
# File: main.py
import dyrel
import time

from dyrel import r, v

class Continent(dyrel.RvObject):
    name: str


europe = Continent(name="Europe")
asia = Continent(name="Asia")
america = Continent(name="America")
africa = Continent(name="Africa")


class Country(dyrel.RvObject):
    name: str
    continent: Continent


france = Country(name="France", continent=europe)
japan = Country(name="Japan", continent=asia)
canada = Country(name="Canada", continent=america)


class City(dyrel.RvObject):
    name: str
    country: Country
    population: int  # in 1_000s of people


cities = dyrel.RvSet([
    City(name="Paris", country=france, population=2_103),
    City(name="Toulouse", country=france, population=511),
    City(name="Bordeaux", country=france, population=265),
    City(name="Tokyo", country=japan, population=9_765),
    City(name="Yokohama", country=japan, population=3_777),
    City(name="Osaka", country=japan, population=2_753),
    City(name="Toronto", country=canada, population=3_026),
    City(name="Montreal", country=canada, population=1_782),
    City(name="Vancouver", country=canada, population=682),
])


def main():
    dyrel.load_file("rel/geography.py")
    dyrel.env["cities"] = cities

    def city_added(sol):
        print(f"Got a European city: {sol.city}!")

    def city_removed(sol):
        print(f"Not a European city: {sol.city}!")

    query = dyrel.query(
        r.city(v.city).in_continent("Europe"),
        on_add=city_added, on_remove=city_removed
    )

    # The following call makes sure the query is up-to-date in our world of perpetual
    # changes. From `query.update()`, the thread will enter the `on_add=` and
    # `on_remove=` callbacks. So in our case, the following will be printed to the
    # console:
    #
    #   Got a European city: Paris!
    #   Got a European city: Toulouse!
    #   Got a European city: Bordeaux!
    query.update()

    # 1. Add London to our geography knowledge base:
    uk = Country(name="UK", continent=europe)
    london = City(name="London", country=uk, population=9_841)
    cities.add(london)

    # The following call with print:
    #   Got a European city: London!
    query.update()

    # 2. Now France travels to Africa. See what happens:
    france.continent = africa

    # This will print:
    #   Not a European city: Bordeaux!
    #   Not a European city: Toulouse!
    #   Not a European city: Paris!
    query.update()

    # 3. Africa is renamed to "Europe". Now technically all the French cities again
    # become located in a continent named "Europe" (we have 2 Europes now), so they
    # all again become European cities:
    africa.name = "Europe"
    # Printing:
    #   Got a European city: Paris!
    #   Got a European city: Toulouse!
    #   Got a European city: Bordeaux!
    query.update()

    # 4. Just adding a new city also works
    cities.add(City(name="Liverpool", country=uk))

    # Printing:
    #   Got a European city: Liverpool!
    query.update()

    # 5. Bordeaux is forgotten
    bordeaux = next(city for city in cities if city.name == "Bordeaux")
    cities.remove(bordeaux)

    # Printing:
    #   Not a European city: Bordeaux!
    query.update()

    # 6. Same thing happens when a city moves to another country:
    london.country = japan

    # Printing:
    #   Not a European city: London!
    query.update()


if __name__ == "__main__":
    main()
    sys.exit(0)
```

This is made possible by the special `RvObject` and `RvSet` base classes. If `obj` is an
instance of `RvObject`, every `obj.attr` reference in a DyRel rule will be automatically
registered as dependency and tracked by the engine: if `obj.attr` changes, the affected
portion of the rule application tree will be recomputed.

The relational code should also be adapted now:

```python
# File: rel/geography.py
from dyrel import r, v, env, obj

r <<= r.city(v.city_name).in_continent(v.continent_name) <= (
    v.city == next(env["cities"]),
    obj(v.city).name(v.city_name),
    obj(v.city).country(v.country),
    obj(v.country).continent(v.continent),
    obj(v.continent).name(v.continent_name),
)
```

That's it, now it's much terser than before as the factual information was moved to
reactive objects and containers in the `europe.py` module. The single rule is hopefully
intuitive enough:

- `dyrel.env` is just a free-form *environment object*. It is used to pass any
  globally-available data to the relational code from normal Python code. It is trackable:
  everything that refers to it in a reactive context is automatically recorded as a
  dependency. Should `dyrel.env["cities"]` change, the dependency is updated. The
  reactivity is fine-grained -- at the level of individual keys.

- `v.city == next(env["cities"])` is a goal that just iterates through whatever iterable
  is assigned to `env["cities"]`. It can be an ordinary Python iterable such as a list or
  dict, or it can be one of the special reactive containers like `RvSet`. The difference
  is that in the former case, nothing will happen when you `.append()` a new element to
  this list, whereas in the latter case, the rule will automatically process the new
  elements.

    (The `env` object defines `__getitem__` which returns special mock objects that define
    `__next__`.)

- `obj(v.city).name(v.city_name)` extracts the attribute `.name` from whatever object the
  variable `v.city` is bound to, and stores the value into the `v.city_name` variable.

    Again, in the same way as with reactive iteration above, if it's just a plain object,
    this code won't be retried when the value of the attribute changes. But if it's an
    `RvObject` instance, then after we do `city.name = "New Name"` in Python, this rule
    will be rerun from this exact spot. In the context of our example above, if
    `london.name = "Londinium"` is executed, then this will be printed:

    ```
    Not a European city: London!
    Got a European city: Londinium!
    ```

    The `obj` is a special wrapper that lets us refer to pure Python attributes as to
    relations. It's not a part of the universal `r`-based namespace structure.

To make this code even simpler, we can add some syntactic sugar:

```python
# File: rel/geography.py
from dyrel import r, v, env, obj

r <<= r.city(v.city_name).in_continent(v.continent_name) <= (
    v.city == next(env["cities"]),
    obj(v.city)(name=v.city_name, country=v.country),
    obj(v.country).continent(v.continent),
    obj(v.continent).name(v.continent_name),
)
```

Here we just combined the two successive goals `obj().name()` and `obj().country()` that
share the same prefix in a single combined goal. We can pass individual continuations to the common prefix as either keyword or positional arguments:

```python
# File: rel/geography.py
from dyrel import r, _r, v, env, obj

r <<= r.city(v.city_name).in_continent(v.continent_name) <= (
    v.city == next(env["cities"]),
    obj(v.city)(_r.name(v.city_name), _r.country(v.country)),
    obj(v.country).continent(v.continent),
    obj(v.continent).name(v.continent_name),
)
```

The `_r` object is completely analogous to the `r` object except that it used to
"continue" a relation name rather than start from the root.


## SQL integration

DyRel can automatically read from SQL tables. Imagine we have this schema:

```sql
CREATE TABLE continent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE country (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    continent_id INTEGER,
    FOREIGN KEY (continent_id) REFERENCES continent(id)
);

CREATE TABLE city (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    country_id INTEGER,
    population INTEGER,
    FOREIGN KEY (country_id) REFERENCES country(id)
);
```

First off, we can just read directly from the database, without mapping anything:

```python
# File: rel/geography.py
from dyrel import r, v, db

## `__setattr__` is defined for the `db` object, so `db.ANYTHING` is supported.
##
## Somewhere in a normal Python module you should have this:
#
# from dyrel import db
#
# db.geo = "sqlite:///geo.db" 
#

geo = db.geo

r <<= r.city(-v.City).from_(-v.Country).in_(+v.Continent) <= (
    sql(
        geo.city(name=v.City, country_id=v.Country_Id),
        geo.country(id=v.Country_Id, name=v.Country, continent_id=v.Continent_Id),
        geo.continent(id=v.Continent_Id, name=v.Continent),
    ),
)
```

The `-` before a variable name (`-v.Country`) means that in this particular rule the
variable is *out* (unbound, free): the rule tries to "fill" such variables by finding all
the possible solutions for them. If a variable is decorated with a `+` (`+v.Country`), it
is an *in* variable: it should be provided (bound, fixed), similar to the usual function
argument. A variable without `+` or `-` is expected to work in both directions. The
variable flow specs can only be specified in the head of a rule. (Variable directions will
be discussed in greater details below.)

In our example, the rule tries to enumerate all the cities with their countries in a given
continent.

That would translate to the following SQL:

```SQL
SELECT
    city.name,
    country.name
FROM
    city
    INNER JOIN country ON city.country_id = country.id
    INNER JOIN continent ON country.continent_id = continent.id
WHERE
    continent.name = :continent
```

Inside an `sql(...)` grouping all the subgoals naturally correspond to the tables in the
*FROM* clause. The joining conditions are easily derived from the matching variables bound
to the columns of the tables. **NOTE** that in this usage, the DyRel layer has absolutely
no knowledge about our database schema. Names like `country` or `continent` are just
assumed to be table names, and keywords inside table goals correspond to column names
whose existence is not checked either. So this is just a fancy SQL query builder.

More about `sql(...)` goal groupings:

- inside an `sql(...)` there can only be referrals to database tables and conditions that
  can be expressed in SQL. That's because ..
- .. the whole `sql(...)` goal is assumed to be executed with a single *SELECT* query;
- if you need to refer to some ordinary DyRel relation, you should do it either before or
  after an `sql(...)` goal;
- even if you want to read just from a single table, you should wrap this goal in an
  `sql(...)` wrapper. This is to mark it explicitly where you have references to the real
  SQL database.

For example, if we did this instead:

```Python
geo = db.geo

r <<= r.city(-v.City).from_(-v.Country).in_(+v.Continent) <= (
    sql(geo.city(name=v.City, country_id=v.Country_Id)),
    sql(geo.country(id=v.Country_Id, name=v.Country, continent_id=v.Continent_Id)),
    sql(geo.continent(id=v.Continent_Id, name=v.Continent)),
)
```

.. that would be something totally different. That would be running

```SQL
SELECT city, country_id FROM city;
```

.. enumerating all the result rows in Python, and for each of them emitting a separate SQL
query:

```SQL
SELECT name, continent_id FROM country WHERE country_id = :country_id
```

.. where `:country_id` is the country ID we just read with the first query, and then
emitting tihs:

```SQL
SELECT 1 FROM continent WHERE id = :continent_id AND name = :name
```

Of course, the engine should use prepared statement or some other form of statement
caching, but you get the idea: that's very inefficient. There should probably be some kind
of linter that would display a warning where 2 `sql(...)` goals go one after another.


## ORM mapping

Now let's do something more interesting: map SQL tables to normal DyRel relations.

```python
# In file: rel/map.py
from dyrel import orm, r, _r, db

geo = db.geo


orm.map_table(
    geo.continent,
    r.continent(),
    columns=[
        orm.Column("id", frozen=True),
        orm.Column("name"),
    ],
    pk="id",
)

orm.map_table(
    geo.country,
    r.country(),
    columns=[
        orm.Column("id", frozen=True),
        orm.Column("name"),
        orm.Column("continent_id"),
    ],
    pk="id",
    fk=[orm.ForeignKey(_r.of_continent(), "continent_id", r.continent())],
)

orm.map_table(
    geo.city,
    r.city(),
    columns=[
        orm.Column("id", frozen=True),
        orm.Column("name"),
        orm.Column("country_id"),
        orm.Column("population"),
    ],
    pk="id",
    fk=[orm.ForeignKey(_r.of_country(), "country_id", r.country())],
)
```

With ORM, as expected, every table row has identity -- it's called a *mapped instance*, or
just *instance*. The mapping calls above set up a set of relations to correspond to mapped
columns and foreign keys. In our example, we now have these relations:

- `r.continent().id()`, `r.continent().name()`;
- `r.country().id()`, `r.country().name()`, `r.country().continent_id()`;
- `r.city().id()`, `r.city().name()`, `r.city().country_id()`, `r.city().population()`;
- foreign keys:
    - `r.country().of_continent()`
    - `r.city().of_country()`

Conceptually, ORM layer caches everything it reads from the database. If a goal

```py
    ...
    r.city(v.city).population(v.pop),
```

.. is reached, where `v.city` is bound and `v.pop` is free, what happens is the `v.city`
instance is first checked for whether it already has its `.population` cached. If it does,
this is just taken to satisfy the goal (the goal would have just 1 solution). Otherwise, a
*SELECT* query is emitted. Queries can be *conglomerated* in 2 axes: for multiple
instances (vertically) and for multiple columns (horizontally) -- more on this in a few
seconds.

So, let's build upon all of this:

```python
# In file: rel/geo.py
from dyrel import r, v

r <<= r.continent(+v.continent).city_name(-v.city_name).of_population(-v.pop) <= (
    r.country(v.country).of_continent(v.continent),
    r.city(v.city).of_country(v.country),
    r.city(v.city).name(v.city_name),
    r.city(v.city).population(v.pop),
)
```

Relation `r.continent(+).city_name(-).of_population(-)` enumerates all the cities with
their populations in a given continent. The first (`continent`) argument is assumed to be
a mapped instance, not just a name. In the first goal
`r.country(v.country).of_continent(v.continent)`, the `v.continent` variable is bound and
the `v.country` is free (as it is encountered for the first time), so this goal just
enumerates all the countries in a given continent. The ORM issues this query:

```sql
SELECT id
FROM country
WHERE continent_id = :continent_id
```

Notice that we only select the absolute minimum of what we need for the mapped entity --
the primary key of the country (`id`).

Now the second goal -- `r.city(v.city).of_country(v.country)` -- is quite similar, we just
enumerate all the cities of a country:

```sql
SELECT id
FROM city
WHERE country_id = :country_id
```

But unlike the pure Database querying with `sql(...)`, the ORM layer is smarter about this
enumeration. The ORM machinery performs what is called *query conglomeration*: instead of
issuing N queries for each country separately, all these requests are collected and then
satisfied by a single SQL query:

```sql
SELECT country_id, id
FROM city
WHERE country_id IN (:country_id_1, :country_id_2, ...)
```

This is how DyRel solves the **N+1 problem**. Evaluation of rules' goals are always
suspended at the DB queries. When we got nothing to do anymore except to run DB queries,
we try to *conglomerate* as much as possible, and issue the minimum amount of queries. In
this way, the primary key lookups and foreign key lookups avoid the *N+1* problem.

But back to our example. Once we got the cities (their IDs), we have still these 2 goals
remaining:

```py
    ...
    r.city(v.city).name(v.city_name),
    r.city(v.city).population(v.pop),
```

Both the `v.city_name` and `v.pop` are free, so we just extract these 2 columns for each
city:

```sql
SELECT name
FROM city
WHERE id IN (:city_id_1, :city_id_2, ...)

SELECT population
FROM city
WHERE id IN (:city_id_1, :city_id_2, ...)
```

DyRel issues 2 queries because these are 2 separate goals. If we try this instead:

```python
# In file: rel/geo.py
from dyrel import r, _r, v

r <<= r.continent(+v.continent).city_name(-v.city_name).of_population(-v.pop) <= (
    r.country(v.country).of_continent(v.continent),
    r.city(v.city)(
        of_country=v.country,
        name=v.city_name,
        population=v.pop,
    ),
)
```

.. then we will be able to reduce the number of queries from 3 down to 1:

```sql
SELECT country_id, id, name, population
FROM city
WHERE country_id IN (:country_id_1, :country_id_2, ...)
```

**NOTE**: it is maybe possible to do smarter optimizations in future versions (e.g. across
different goals).


### Double direction for foreign keys

Foreign key relations like `r.city().country()` can work in 2 modes:

- forward: `r.city(+).country(-)` just reads the `country_id` column for a given `city`
  instance (if it's not loaded yet) and returns the country instance that corresponds to
  it;
- backward: `r.city(-).country(+)` finds all the cities that belong to a particular
  country. The country's `id` is used to query for `city.id`, for each of which the
  respective `city` instance is returned.

Therefore, we don't need 2 relations on each side of the foreign key, as is the case in
many ORM systems.


## Mutations in the ORM layer

As already noted in the introduction, DyRel takes a very different approach to SQL data
manipulation than conventional ORM frameworks. You cannot just assign directly to
attributes of mapped instances; instead, what you do is still the same thing: build
relations and compute derived data. Only this time what you compute is the data
*describing what needs to be changed*. The changes themselves are then applied outside of
the relational engine.

Let's see an example to illustrate:

```python
# In file: rel/geo.py
from dyrel import r, _r, db, fork


OVERPOPULATED_LIMIT = 3500


r <<= r.consider_moving_city(+v.city).to_country(+v.country).do(-v.do) <= (
    r.city(v.city).population(v.pop),
    v.pop > OVERPOPULATED_LIMIT,
    r.city(v.city).set(v.do).of_country(v.country),
)

r <<= r.move_overpopulated_cities.from_(+v.source_country)
        .to(+v.target_country)
        .do(-v.do) <= (
    r.city(v.city).of_country(v.source_country),
    r.consider_moving_city(v.city).to_country(v.target_country).do(v.do),
)

r <<= r.consider_population_reduction(+v.city).do(-v.do) <= (
    r.city(v.city).population(v.pop),
    v.pop > OVERPOPULATED_LIMIT,
    v.new_pop == v.pop - 500,
    r.city(v.city).set(v.do).population(v.new_pop),
)

r <<= r.reduce_overpopulated_cities.of_country(+v.country).do(-v.do) <= (
    r.city(v.city).of_country(v.country),
    r.consider_population_reduction(v.city).do(v.do),
)


r <<= r.address_overpopulation.do(-v.do) <= (
    r.country(v.japan).name("Japan"),
    r.country(v.france).name("France"),
    fork(
        r.move_overpopulated_cities.from_(v.japan).to(v.france).do(v.do),
        r.reduce_overpopulated_cities.of_country(v.france).do(v.do),
    ),
)
```

There's relation `r.consider_moving_city(+).to_country(+).do(-)`, and it is just a normal relation in all respects. The last of its arguments, `v.do`, is "forwarded" to `r.city(+).of_country(+).do(-)` where it's bound. This latter predicate
