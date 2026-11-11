import asyncio
import logging
from threading import Event

from lsprotocol import types as lsp
from pygls.io_ import run_async
from pygls.lsp.server import LanguageServer


async def run_lsp_server():
    tcp_server = await asyncio.start_server(lsp_connection, "127.0.0.1", 17017)
    async with tcp_server:
        await tcp_server.serve_forever()


async def lsp_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    lsp_server = make_lsp_server()
    lsp_server.protocol.set_writer(writer)

    await run_async(
        stop_event=Event(),
        reader=reader,
        protocol=lsp_server.protocol,
        logger=logging.getLogger(),
        error_handler=lsp_server.report_server_error,
    )


def make_lsp_server() -> LanguageServer:
    lsp_server = LanguageServer("dyrel", "0.1")

    @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def hover(params: lsp.HoverParams) -> lsp.Hover:
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.PlainText,
                value=f"Dyrel LSP says: {params.position.line}:{params.position.character}",
            )
        )

    return lsp_server
