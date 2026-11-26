from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(eq=False, repr=False, init=True, slots=True)
class LspClient:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    name: str | None = None
    next_req_id: int = 1
    pending_requests: dict = field(default_factory=dict)

    @property
    def is_initialized(self) -> bool:
        return self.name is not None
