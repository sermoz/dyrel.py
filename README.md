# DyRel

*DyRel* (for *Dynamic Relations*) is a Python-embedded relational engine featuring
incremental evaluation, reactivity, SQL integration, and first-class support for live
interactive development. It is based on the
[Datalog](https://en.wikipedia.org/wiki/Datalog) language.

**NOTE: Project is in early development. What follows below is the current vision of the
author. Everything beyond the general feel and spirit is subject to change.**

DyRel can be regarded as a deductive in-memory database. A deductive database has some
basic data (called *facts*) and also *rules* of deducing new data from existing ones. All
the information is represented with relations -- same as in normal _relational databases_
such as MySQL or PostgreSQL, where relations are just usually called _tables_
-- but some of these relations can be specified with rules, not just pure data, and
evaluated lazily (on demand). Should anything change in the source data, the deduced one
is recomputed incrementally, i.e. only the affected portion of the rule-based relation is
re-derived.

DyRel is designed to be a "business logic engine" for Python applications. It should be
able to handle most of the rules and logic of the domain model, leaving pure Python to do
the high-level orchestration and glue different subsystems together.

