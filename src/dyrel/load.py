from __future__ import annotations

import enum
import traceback
from dataclasses import dataclass
from pathlib import Path


def load_dir(dir):
    source_files: dict[Path, Source_File] = {}

    for py_path in Path(dir).glob("*.py"):
        source_file = Source_File(path=py_path, state=Source_File_State.Ok)
        source_files[str(py_path)] = source_file

        try:
            code = compile(py_path.read_bytes(), filename=f"dyrel::{py_path}", mode="exec")
        except Exception:
            # print(f"Compilation error in {file}:\n{e}\n")
            traceback.print_exc()
            source_file.state = Source_File_State.Failed_To_Compile
            continue

        try:
            exec(code)
        except Exception:
            traceback.print_exc()
            source_file.state = Source_File_State.Raised_At_Exec
            continue

    return source_files


@dataclass(eq=False, slots=True)
class Source_File:
    path: Path
    state: Source_File_State


class Source_File_State(enum.Enum):
    Failed_To_Compile = enum.auto()
    Raised_At_Exec = enum.auto()
    Ok = enum.auto()


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
