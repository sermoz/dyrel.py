from __future__ import annotations

import enum
import traceback
from dataclasses import dataclass
from pathlib import Path


def load_dir(dir):
    source_files: dict[Path, SourceFile] = {}

    for py_path in Path(dir).glob("*.py"):
        source_file = SourceFile(path=py_path, state=SourceFileState.OK)
        source_files[str(py_path)] = source_file

        try:
            code = compile(py_path.read_bytes(), filename=f"dyrel::{py_path}", mode="exec")
        except Exception:
            # print(f"Compilation error in {file}:\n{e}\n")
            traceback.print_exc()
            source_file.state = SourceFileState.FAILED_TO_COMPILE

            continue

        try:
            exec(code)
        except Exception:
            traceback.print_exc()
            source_file.state = SourceFileState.RAISED_AT_EXEC
            continue

    return source_files


@dataclass(eq=False, slots=True)
class SourceFile:
    path: Path
    state: SourceFileState


class SourceFileState(enum.Enum):
    FAILED_TO_COMPILE = enum.auto()
    RAISED_AT_EXEC = enum.auto()
    OK = enum.auto()


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
