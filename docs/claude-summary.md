# Dyrel — design summary

Positioning. Practical Earth-programming tool: a SQLAlchemy substitute with Datalog bones, not a Differential Datalog competitor. Session-scale data. Single-writer: every write flows through the Dyrel session, which persists to MySQL — so deltas are always observed natively. No binlog/CDC; foreign writers out of scope for v1. SQL = persistence backend + cold-path evaluator, never the delta source.

## Evaluation architecture (Rete-family with three amendments).

Top-down, demand-driven. Projections (predicate + adornment + bound values) are first-class demanded objects in hash tables — including empty ones: (contents ∅, completeness certificate, consumers, demand support).
TREAT, not Rete: no beta memories. Durably materialized = semantic objects only (projection contents, certificates, support counts, derived predicate contents). Continuations (stalled records / tree nodes — isomorphic; records favored, pointers legal as caches but never load-bearing) are disposable resumption state: dropped per (rule, adornment) on replan, rebuilt from semantic caches. Exactly one consumer population per (rule, adornment).
Network fragments exist only under demanded (rule, adornment) pairs — the magic-sets restriction, structurally. Demand entries are support-counted; when a prefix dies the subscription GCs (contents may remain as passive cache).
Negation = demand entry with inverted polarity. Aggregation reads strictly lower strata; recursion-through-aggregation banned (dependency-graph check).

## Planning.

Plans memoized per (rule, adornment), compiled lazily on first demand. Mode inference runs in the same pass: demand-driven top-down per rule, memoized — no global bottom-up closure.
Leaf mode signatures: EDB = any adornment; SQL tables = any (ff flaggable); builtins/comparisons carry the real constraints (bb). Builtin table hard-coded with check-augmented modes.
Signatures are upward-closed adornment sets; store the minimal frontier. Closure decides legality; each demanded adornment is still planned natively. Unsupported adornments propagate up through demand; errors name (definition, use, unbindable variable); distinct warning when a builtin never legalizes.
Greedy ordering, ahistorical (current adornment vs. static signature only): eligible = legal; then (1) check/≤1 atoms fire immediately upon legalization, (2) generators — extra-bound (strictly above a minimal adornment) before bare-legal (= minimal; the unified scan tier), (3) written order. No bound-arg counting, no binding-order sensitivity. Predictability over optimality; MySQL's optimizer covers the cold path.
Determinism buckets {check, ≤1, ≤n, many} per (predicate, adornment). v0: internal only, derived structurally — builtins, fully-bound atoms, -> with keys bound ⇒ ≤1, SQL PK/UNIQUE. v1: optional user hints — coarse, absolute, local, cost-only (never cut semantics), runtime-checked with warnings. Relative == constraints dropped.

## Incremental maintenance.

One delta rule per body occurrence; evaluation walks outward from the Δ tuple.
Table-backed bodies: the composed SQL delta query is the executor (Δ row's values substituted, joins around it), SELECTing all intermediate variables to refresh intermediate contents, counts, and emissions in one round trip. Delete = same query with old values, negative polarity; update = delete + insert. One session write processed per flush (no Δ⋈Δ cross-terms). This is first-order IVM; DBToaster-style higher-order is the upgrade path if delta queries ever get hot.
Mixed bodies: maximal table-backed subchain → one SQL query; remainder joined in memory. Delta algebra is substrate-independent; executor chosen per leaf.
Retraction = subtree walk gated by decrements: within-rule derivation trees are uniquely owned (unconditional delete); all sharing lives at membranes (each rule's output layer: derived tuples, demand entries, root answers) carrying support counts. Decrement once per dying path; zero → cross the membrane and recurse; positive → stop. Self-join idempotence. Polarity flips through negation.
Emission gate: external deltas on 0↔1 transitions only, emitted after the round settles (glitch-free), at transaction ticks. Root subscription = (added, removed) stream, plus updated(key, old, new) for functional predicates.

## Recursion & GC.

Counting is exact in acyclic regions. Recursion handled by witness GC: each derivation-graph node keeps refcounts plus one distinguished acyclic witness edge. Non-witness edge death = plain decrement. Witness death → end-of-round candidate set → adopt another live incoming edge under the acyclicity guard (witness chain reaches base facts without passing the candidate; memoized per round); no adoption → garbage → cascade. Witness structure lives on the derivation AND-OR graph only; base facts are the roots. SCC-confined recompute remains the fallback.
Demand side stays pure refcounting; demand cycles broken tabling-style (a subgoal demanding itself subscribes to the open table rather than re-opening it).
Two distinct refcount graphs: derivation support (roots = base facts) and demand support (roots = root goals + live cells). Demand hitting zero demotes contents to passive cache — no retraction.
Passive cache is resource policy, not liveness: v0 session-scoped (dies at session close); later size-capped LRU, evicting contents and certificate together. Identity cells weakly referenced when unwatched, kept strong by live subscriptions.
Python-level hygiene: no pointer cycles (records and keys, no back-pointers; cells hold subscriber keys), __slots__/plain tuples, interned environments and row tuples, per-transaction batching, gc.freeze only if profiling demands.

## Caching & SQL boundary.

Semantic caching unit: completeness certificate per (projection, adornment, bound prefix). Empty-but-certified is knowledge (negative caching). Certificates survive deletes (single-writer) and transfer only downward in boundness (subsumption by filtering, never widening).
Fine-grained gap/interval facts are deferred to the sorted-structure/LFTJ world (v2); v0's hash world uses prefix completeness only.
Cache miss = targeted SQL with WHERE from the bound prefix, seeding caches; demand widening (new root constants) rides the same path.
sql(...) blocks: explicit boundary annotation; contents must be entirely SQL-compilable (native predicates inside = compile error). A block is an opaque virtual leaf — projections, certificates, consumers at block granularity, keyed by head adornment. Snapshot semantics: no internal incrementality; session writes to mentioned tables invalidate block caches; live consumers re-query next tick; the boundary set-diff feeds normal ± propagation, so blocks remain live. sql_incremental(...) is a later opt-in behind the identical interface.

## Semantics & data model.

Set semantics for rules (0↔1 emission gate). Bag behavior arises from identity arguments, not an engine mode; aggregates fold set-deltas of key-carrying input projections grouped by FD keys. Aggregating a projection whose head dropped identity vars = lint/type error. min/max keep their input projection resident for extremum retraction; avg = (sum, n).
Functional dependencies in syntax: p(K…) -> V… (LogicBlox bracket sugar p[K…] = V worth adopting). Left of arrow = identity: interned, probed, joined, counted, is-stable. Right = state: never hashed or joined, updated in place, per-field subscriptions, updated-deltas.
FD conflict policy declared at the arrow: plain = V is unique-or-error (v0 default; raises incrementally, citing witnesses), = sum(V)-style folds restore the FD by aggregation, = lub(V) lattice-merge deferred (keeps the monotone/CRDT door open).
Identity cells ≡ functional predicates: cell key = key args, fields = functional positions, one interning table, session-scoped, hit → in-place mutation, key death → retire. Fields hold values/keys only; nested reactive objects = nested cells.

Storage (v0). Python dicts/sets/tuples: demand tables as dict[b-values] → set[f-residuals]; per-adornment hash indexes on base relations; flat dicts for counts and cells; interned row tuples. No in-memory ordered seek or ranges (ranges go to SQL or scan). The projection interface (probe by prefix, iterate residuals, ±1) is the stable contract so sorted arrays / lazy tries / LFTJ / Free Join can slot in at v2 without touching the network.

Open items. Recursion rollout (witness GC lands with it); fold-valued cells × witness GC interaction; fully-bound probe against -> with a contradicting value — fail vs. raise, decide once; static FD checking (v1); certificate-invalidation discipline under the growing feature set.
