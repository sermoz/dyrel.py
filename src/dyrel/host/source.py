from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dyrel.relation import Query, QueryKey, RelationFactSupport


ROOT_DIR: Path
FILE_BY_PATH: dict[Path, SourceFile] = {}
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
