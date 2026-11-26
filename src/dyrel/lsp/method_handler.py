from __future__ import annotations

from typing import TYPE_CHECKING

from lsprotocol import types as lsp

if TYPE_CHECKING:
    from dyrel.lsp.client import LspClient


METHOD_HANDLERS = {}


def handler(method: str):
    def decorator(handler):
        assert method not in METHOD_HANDLERS

        METHOD_HANDLERS[method] = handler
        return handler

    return decorator


@handler(lsp.INITIALIZE)
def on_initialize(cli: LspClient, params: lsp.InitializeParams) -> lsp.InitializeResult:
    # TODO: handle the case when the client is already initialized
    cli.name = params.client_info.name if params.client_info else "<Unnamed>"

    return lsp.InitializeResult(
        server_info=lsp.ServerInfo(name="Dyrel", version="0.1"),
        capabilities=lsp.ServerCapabilities(
            position_encoding=lsp.PositionEncodingKind.Utf16,
            # position_encoding="utf-16",
        ),
    )


def register_capabilities(client: LspClient):
    # TODO: this should belong to another module most likely
    pass
