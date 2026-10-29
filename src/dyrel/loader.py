from __future__ import annotations
import itertools

import enum
import hashlib
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, TypeAlias

from dyrel.relation import Record, RelApp, Relation
from dyrel import util

SOURCE_FILE_REGISTRY: dict[Path, SourceFile] = {}
QUERIES_BY_FILE: dict[SourceFile, set[Query]] = {}


@dataclass(eq=False, repr=False, slots=True)
class SourceFile:
    path: Path
    digest: bytes
    state: SourceFileState
    facts: RecordSupportMap | None = None


RecordSupportMap: TypeAlias = defaultdict[Relation, Counter[Record]]


class SourceFileState(enum.Enum):
    FAILED_TO_COMPILE = enum.auto()
    FAILED_TO_RUN = enum.auto()
    OK = enum.auto()


@dataclass(eq=True, frozen=True, slots=True)
class Query:
    name: str
    rel_app: RelApp


def reload_dir(dir: Path):
    """(Re)load all the directory's *.py files"""
    change = Change()

    for path in dir.glob("*.py"):
        reload_file(change, path)

    # change.apply_delta_facts()
    apply_and_report_change(change)

    total_support = sum(delta.total() for delta in change.delta_facts.values())
    print(f'Dir "{dir}" reload: loaded {total_support} facts for {len(change.delta_facts)} relations')


def reload_file(change: Change, path: Path):
    """Reload the file given by 'path' and contribute to 'change'.

    Global data structures are updated eagerly. Changes in records (added/removed) are
    accumulated in 'change' and not updated here.
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
            state=SourceFileState.OK,  # just to init
            facts=None,
        )

    source_file.state = result.state
    source_file.digest = digest

    # Be sure not to remove the old facts if the file is broken.
    if not isinstance(result, LoadSuccess):
        return

    change.update(
        old_facts=source_file.facts,
        new_facts=result.facts,
        new_queries=result.queries - QUERIES_BY_FILE.get(source_file, set())
    )

    if result.queries:
        QUERIES_BY_FILE[source_file] = result.queries
    else:
        QUERIES_BY_FILE.pop(source_file, None)

    source_file.facts = result.facts


@dataclass(eq=False, frozen=True, slots=True)
class LoadSuccess:
    state: ClassVar = SourceFileState.OK

    facts: RecordSupportMap
    queries: set[Query]


@dataclass(eq=False, frozen=True, slots=True)
class LoadFailure:
    # On load failure, 'facts' of a module don't exist
    facts: ClassVar = None

    state: SourceFileState


LoadResult: TypeAlias = LoadSuccess | LoadFailure


# Global variable that are non-None only during a source file load. At all other times,
# they both are None.
cur_file_facts: RecordSupportMap | None = None
cur_file_queries: set[Query] | None = None


def load_file(path: Path, file_contents: bytes) -> LoadResult:
    try:
        code_obj = compile(file_contents, filename=f"dyrel::{path}", mode="exec")
    except Exception:
        traceback.print_exc()
        return LoadFailure(SourceFileState.FAILED_TO_COMPILE)

    global cur_file_facts, cur_file_queries

    cur_file_facts = defaultdict(Counter)
    cur_file_queries = set()

    try:
        exec(code_obj)
    except Exception:
        traceback.print_exc()
        return LoadFailure(SourceFileState.FAILED_TO_RUN)
    else:
        return LoadSuccess(facts=cur_file_facts, queries=cur_file_queries)
    finally:
        cur_file_facts = None
        cur_file_queries = None


@dataclass(eq=False, slots=True)
class Change:
    delta_facts: RecordSupportMap = field(default_factory=lambda: defaultdict(Counter), init=False)
    new_queries: set[Query] = field(default_factory=set, init=False)

    def update(self, old_facts: RecordSupportMap | None, new_facts: RecordSupportMap, new_queries: set[Query]):
        if old_facts:
            for rel in old_facts:
                self.delta_facts[rel].subtract(old_facts[rel])

        for rel in new_facts:
            self.delta_facts[rel].update(new_facts[rel])

        self.new_queries.update(new_queries)

    def normalize(self):
        """Throw away all the net 0 entries from 'facts' counters."""
        to_del = []

        for rel, delta in self.delta_facts.items():
            for rec in [rec for rec, d in delta.items() if d == 0]:
                del delta[rec]

            if not delta:
                to_del.append(rel)

        for rel in to_del:
            del self.delta_facts[rel]

    def apply_delta_facts(self):
        for rel, delta in self.delta_facts.items():
            rel.records += delta


def apply_and_report_change(change: Change):
    change.normalize()

    existed_queries_by_rel = util.group_by(
        {query for queries in QUERIES_BY_FILE.values() for query in queries} - change.new_queries,
        key=lambda query: query.rel_app.rel
    )

    for rel, delta in change.delta_facts.items():
        if rel not in existed_queries_by_rel:
            continue

        added, removed = compute_added_removed_records(rel, delta)

        for query in existed_queries_by_rel[rel]:
            q_added = {rec for rec in added if query.rel_app.is_satisfied_by_record(rec)}
            q_removed = {rec for rec in removed if query.rel_app.is_satisfied_by_record(rec)}

            if not q_added and not q_removed:
                continue

            print(f'Query "{query.name}":')

            for rec in q_added:
                print(f'  +{rec}')

            for rec in q_removed:
                print(f'  -{rec}')

    change.apply_delta_facts()

    # Process the "new queries" separately: they need all the records, not just delta
    new_queries_by_rel = util.group_by(
        change.new_queries, key=lambda query: query.rel_app.rel
    )

    for rel, queries in new_queries_by_rel.items():
        for query in queries:
            print(f'New query "{query.name}":')

            for rec in rel.records:
                if query.rel_app.is_satisfied_by_record(rec):
                    print(f'  {rec}')


def compute_added_removed_records(rel: Relation, delta: Counter[Record]) -> tuple[set[Record], set[Record]]:
    # `rec not in rel.records` implies that `delta[rec] > 0`
    added = {rec for rec in delta if rec not in rel.records}
    removed = {rec for rec in delta if delta[rec] == -rel.records[rec]}

    return added, removed
