from __future__ import annotations
from typing import ClassVar

import asyncio
import enum
import traceback
from dataclasses import dataclass
from pathlib import Path

from .relation import Fact

source_file_registry: dict[str, SourceFile] = {}


@dataclass(eq=False, repr=False, slots=True)
class SourceFile:
    path: Path
    state: SourceFileState
    facts: set[Fact] | None = None
    timestamp: int  # corresponds to os.stat_result.st_mtime_ns


class SourceFileState(enum.Enum):
    FAILED_TO_COMPILE = enum.auto()
    RAISED_AT_EXEC = enum.auto()
    OK = enum.auto()



def reload_dir(dir):
    """(Re)load all the directory's *.py files"""
    source_files: dict[Path, SourceFile] = {}

    for path in Path(dir).glob("*.py"):
        pass

    return source_files


facts_being_loaded: list[Fact] | None = None


def load_file(path: Path) -> SourceFile:
    try:
        code = compile(path.read_bytes(), filename=f"dyrel::{path}", mode="exec")
    except Exception:
        # print(f"Compilation error in {path}:\n{e}\n")
        traceback.print_exc()
        return SourceFile(path=path, state=SourceFileState.FAILED_TO_COMPILE)

    global facts_being_loaded
    facts_being_loaded = []

    try:
        exec(code)
    except Exception:
        traceback.print_exc()
        return SourceFile(path=path, state=SourceFileState.RAISED_AT_EXEC)
    else:
        return SourceFile(path=path, state=SourceFileState.OK, facts=set(facts_being_loaded))
    finally:
        facts_being_loaded = None


def main():
    source_files = load_dir("sample")

    print(f"Loaded {len(source_files)} files:")

    for path in source_files:
        print(path)

    import IPython

    from dyrel.relation import relation_registry

    IPython.embed(colors="neutral", user_ns={
        "source_files": source_files,
        "reg": relation_registry
    })
