from __future__ import annotations

import enum
import hashlib
import traceback
from dataclasses import dataclass
from pathlib import Path

from .relation import Fact, Relation

source_file_registry: dict[Path, SourceFile] = {}


@dataclass(eq=False, repr=False, slots=True)
class SourceFile:
    path: Path
    state: SourceFileState
    digest: bytes
    # do we need this? timestamp: int  # corresponds to os.stat_result.st_mtime_ns
    facts: set[Fact] | None = None


class SourceFileState(enum.Enum):
    FAILED_TO_COMPILE = enum.auto()
    RAISED_AT_EXEC = enum.auto()
    OK = enum.auto()


def reload_dir(dir: Path):
    """(Re)load all the directory's *.py files"""
    total_affected_rels = set()

    for path in dir.glob("*.py"):
        affected_rels = reconsider_file(path)

        if affected_rels is not None:
            print(f'File "{path}": affected {len(affected_rels)} relations')
            total_affected_rels |= affected_rels

    print(f'Dir "{dir}" reload: affected {len(total_affected_rels)} relations')


def reconsider_file(path: Path) -> set[Relation] | None:
    file_contents = path.read_bytes()
    digest = hashlib.blake2b(file_contents, digest_size=32).digest()

    source_file = source_file_registry.get(path)

    if source_file is not None and source_file.digest == digest:
        return

    # Need to load
    state, facts = load_file(path, file_contents)

    if source_file is None:
        source_file_registry[path] = SourceFile(
            path=path,
            state=state,
            digest=digest,
            facts=facts,
        )
        for fact in facts:
            fact.rel.records.add(fact.rec)
        return {fact.rel for fact in facts}

    # Be sure not to remove the old facts if the file is broken.
    source_file.state = state
    source_file.digest = digest

    if state != SourceFileState.OK:
        # If the file becomes broken, all the ghost facts are preserved.
        print(f'File "{path}" broke: {state}')
        return

    # Compare old and new facts
    old_facts = source_file.facts or set()

    to_add = facts - old_facts
    to_rem = old_facts - facts

    for fact in to_rem:
        fact.rel.records.remove(fact.rec)
    for fact in to_add:
        fact.rel.records.add(fact.rec)

    source_file.facts = facts

    return {fact.rel for fact in to_add | to_rem}


facts_being_loaded: list[Fact] | None = None


def load_file(path: Path, file_contents: bytes) -> tuple[SourceFileState, set[Fact] | None]:
    try:
        code_obj = compile(file_contents, filename=f"dyrel::{path}", mode="exec")
    except Exception:
        # print(f"Compilation error in {path}:\n{e}\n")
        traceback.print_exc()
        return SourceFileState.FAILED_TO_COMPILE, None

    global facts_being_loaded
    facts_being_loaded = []

    try:
        exec(code_obj)
    except Exception:
        traceback.print_exc()
        return SourceFileState.RAISED_AT_EXEC, None
    else:
        return SourceFileState.OK, set(facts_being_loaded)
    finally:
        facts_being_loaded = None
