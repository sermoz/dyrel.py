from __future__ import annotations

import enum
import hashlib
import traceback
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeAlias, cast

from dyrel import update
from dyrel.exc import DyrelError
from dyrel.relation import Query, Record, RelApp, Slice

if TYPE_CHECKING:
    from dyrel.dsl import RelAppLink, Val
    from dyrel.relation import QueryKey, RelationFactSupport


SOURCE_FILE_REGISTRY: dict[Path, SourceFile] = {}
QUERIES_BY_FILE: dict[SourceFile, dict[QueryKey, Query]] = {}


@dataclass(eq=False, repr=False, slots=True)
class SourceFile:
    path: Path
    digest: bytes
    state: SourceFileState
    facts: RelationFactSupport | None = None


class SourceFileState(enum.Enum):
    FAILED_TO_COMPILE = enum.auto()
    FAILED_TO_RUN = enum.auto()
    OK = enum.auto()


@dataclass(eq=False, repr=False, slots=True)
class QueryDef:
    """How queries come from source files."""

    name: str
    rel_app: RelApp
    callback: Callable


def query(chain: RelAppLink):
    """Entry-point decorator to be used in Dyrel source files.

    Example:
        @query(r.person(v.Person).aunt("Jinny"))
        def _jinny_nephews(appeared, Person):
            if appeared:
                print(f'{Person} is a nephew of Jinny')
            else:
                print(f'{Person} is no longer a nephew of Jinny')
    """
    goal = RelApp.from_chain(chain)

    if len(goal.var_names) > len(set(goal.var_names)):
        raise DyrelError("Duplicated var names in a goal")

    def wrapper(callback):
        if not isinstance(getattr(callback, "__name__", None), str):
            raise DyrelError('Query handler callable has no "__name__"')

        return QueryDef(
            name=callback.__name__,
            rel_app=goal,
            callback=callback,
        )

    return wrapper


def reload_dir(dir: Path):
    """(Re)load all the directory's *.py files"""
    rel_deltas: RelationFactSupport = defaultdict(Counter)

    for path in dir.glob("*.py"):
        reload_file(rel_deltas, path)

    update.apply_delta_facts(rel_deltas)
    update.process_stale_queries()


def reload_file(rel_deltas: RelationFactSupport, path: Path):
    """Reload the file given by 'path' and contribute to 'change'.

    Global data structures are updated eagerly. Changes in facts are netted in 'delta' and
    applied at the end of the reload transaction.
    """
    file_contents = path.read_bytes()
    digest = hashlib.blake2b(file_contents, digest_size=32).digest()

    source_file = SOURCE_FILE_REGISTRY.get(path)

    # Did the file changed?
    if source_file is not None and source_file.digest == digest:
        return

    result = load_file(path, file_contents)

    if source_file is None:
        source_file = SOURCE_FILE_REGISTRY[path] = SourceFile(
            path=path,
            digest=digest,
            state=result.state,
            facts=None,
        )
    else:
        source_file.state = result.state
        source_file.digest = digest

    # Be sure not to remove the old facts if the file is broken.
    if not isinstance(result, LoadSuccess):
        return

    # Process facts
    if source_file.facts:
        for rel, counter in source_file.facts.items():
            rel_deltas[rel].subtract(counter)

    for rel, counter in result.facts.items():
        rel_deltas[rel].update(counter)

    source_file.facts = result.facts

    # Process queries
    reconcile_queries(source_file, result.query_defs)


def reconcile_queries(source_file: SourceFile, query_defs: list[QueryDef]):
    if not (source_file in QUERIES_BY_FILE or query_defs):
        # Had no queries, still has no queries => nothing to do
        return

    query_by_key = QUERIES_BY_FILE.setdefault(source_file, {})
    unseen_queries = set(query_by_key.values())

    for qdef in query_defs:
        slyce = Slice.for_rel_app(qdef.rel_app)

        if (qdef.name, slyce) in query_by_key:
            # Update existing query with the new callback and other info
            x_query = query_by_key[qdef.name, slyce]

            x_query.var_names = qdef.rel_app.var_names
            x_query.callback = qdef.callback

            unseen_queries.remove(x_query)
        else:
            # Create new Query instance
            query = query_by_key[qdef.name, slyce] = Query(
                name=qdef.name,
                slyce=slyce,
                var_names=qdef.rel_app.var_names,
                callback=qdef.callback,
            )
            query.invalidate()

    for query in unseen_queries:
        query.unlink()
        del query_by_key[query.key]

    if not query_by_key:
        del QUERIES_BY_FILE[source_file]


@dataclass(eq=False, frozen=True, slots=True)
class LoadSuccess:
    state: ClassVar = SourceFileState.OK

    facts: RelationFactSupport
    query_defs: list[QueryDef]


@dataclass(eq=False, frozen=True, slots=True)
class LoadFailure:
    facts: ClassVar = None  # On load failure, 'facts' of a file don't exist

    state: SourceFileState


LoadResult: TypeAlias = LoadSuccess | LoadFailure


# Not a None only during a source file load.
cur_file_facts: RelationFactSupport | None = None


def load_file(path: Path, file_contents: bytes) -> LoadResult:
    try:
        code_obj = compile(file_contents, filename=f"dyrel:{path}", mode="exec")
    except Exception:
        traceback.print_exc()
        return LoadFailure(SourceFileState.FAILED_TO_COMPILE)

    global cur_file_facts

    namespace = {}
    cur_file_facts = defaultdict(Counter)

    try:
        exec(code_obj, namespace)
    except Exception:
        traceback.print_exc()
        return LoadFailure(SourceFileState.FAILED_TO_RUN)
    else:
        return LoadSuccess(
            facts=cur_file_facts,
            query_defs=[
                qdef for qdef in namespace.values() if isinstance(qdef, QueryDef)
            ],
        )
    finally:
        cur_file_facts = None


def register_fact(chain: RelAppLink):
    if cur_file_facts is None:
        raise DyrelError('"r += ..." in a context where it\'s not expected')

    app = RelApp.from_chain(chain)

    if not app.is_ground:
        raise DyrelError("We cannot yet define rules, only ground facts")

    cur_file_facts[app.rel][Record(cast("Val", val).value for val in app.args)] += 1
