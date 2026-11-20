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

    content_length = 0
    logger = logger or logging.getLogger(__name__)

    while not stop_event.is_set():
        # Read a header line
        header = await reader.readline()
        if not header:
            break

        # Extract content length if possible
        if not content_length:
            match = CONTENT_LENGTH_PATTERN.fullmatch(header)
            if match:
                content_length = int(match.group(1))
                logger.debug("Content length: %s", content_length)

        # Check if all headers have been read (as indicated by an empty line \r\n)
        if content_length and not header.strip():
            # Read body
            body = await reader.readexactly(content_length)
            if not body:
                break

            try:
                message = json.loads(body, object_hook=protocol.structure_message)
                protocol.handle_message(message)
            except Exception as exc:
                logger.exception("Unable to handle message")
                if error_handler:
                    error_handler(exc, JsonRpcException)
            finally:
                # Reset
                content_length = 0


CONTENT_LENGTH_PATTERN = re.compile(rb"^Content-Length: (\d+)\r\n$")


async def read_headers(reader: asyncio.StreamReader):
    line = await reader.readline()
    if not line:
        raise ClientDisconnect

    if not line.endswith(b"\r\n"):
        raise ClientDisconnect


# @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
# def hover(ls: LanguageServer, params: lsp.HoverParams) -> lsp.Hover:
#     return lsp.Hover(
#         contents=lsp.MarkupContent(
#             kind=lsp.MarkupKind.PlainText,
#             value=f"Dyrel: {list(ls.workspace.text_documents)}",
#         )
#     )
