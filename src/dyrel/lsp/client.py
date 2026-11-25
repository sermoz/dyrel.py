from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(eq=False, repr=False, init=False, slots=True)
class LspClient:
    name: str | None = None
    next_req_id: int = 1
    pending_requests: dict = field(default_factory=dict)

    @property
    def is_initialized(self) -> bool:
        return self.name is not None
