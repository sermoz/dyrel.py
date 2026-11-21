from __future__ import annotations

import asyncio
import logging.config
import re

logger = logging.getLogger("dyrel.lsp")


async def run_lsp_server():
    tcp_server = await asyncio.start_server(serve_lsp_client, "127.0.0.1", 17017)
    async with tcp_server:
        await tcp_server.serve_forever()


async def serve_lsp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

    while True:
        headers = await read_headers(reader)

        try:
            content_length = int(headers[b"Content-Length"])
        except Exception:
            logger.error(
                "Invalid 'Content-Length' header: '%s'",
                headers.get(b"Content-Length", "(missing)"),
            )
            raise Stop

        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError:
            logger.debug("Could not read the whole message from the client, quitting")
            raise Stop

        # try:
        #     message = json.loads(body, object_hook=protocol.structure_message)
        #     protocol.handle_message(message)
        # except Exception as exc:
        #     logger.exception("Unable to handle message")
        #     if error_handler:
        #         error_handler(exc, JsonRpcException)
        # finally:
        #     # Reset
        #     content_length = 0


RE_HEADER = re.compile(rb"([^:]+?): (.+)\r\n")


async def read_headers(reader: asyncio.StreamReader) -> dict[bytes, bytes]:
    headers = {}

    while True:
        line = await reader.readline()

        if not line.endswith(b"\n"):
            # Client disconnected, possibly mid-header
            raise Stop

        if line == b"\r\n":
            break

        mres = re.fullmatch(RE_HEADER, line)

        if mres is None:
            logger.error("Failed to parse LSP client header: '%s'", line)
            raise Stop

        header, value = mres.groups()
        headers[header] = value

    return headers


class Stop(Exception):
    pass


# class


# @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
# def hover(ls: LanguageServer, params: lsp.HoverParams) -> lsp.Hover:
#     return lsp.Hover(
#         contents=lsp.MarkupContent(
#             kind=lsp.MarkupKind.PlainText,
#             value=f"Dyrel: {list(ls.workspace.text_documents)}",
#         )
#     )
