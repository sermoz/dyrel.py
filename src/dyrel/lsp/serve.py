from __future__ import annotations

import asyncio
import json
import logging.config
import re
from typing import cast

import lsprotocol.converters
from lsprotocol import types as lsp

from dyrel.lsp.client import LspClient

lsp_converter = lsprotocol.converters.get_converter()


logger = logging.getLogger("dyrel.lsp")


MAX_RPC_MESSAGE_LENGTH: int = 100 << 10


async def run_lsp_server():
    tcp_server = await asyncio.start_server(serve_lsp_client, "127.0.0.1", 17017)
    async with tcp_server:
        await tcp_server.serve_forever()


async def serve_lsp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger.info("New LSP client connected!")

    try:
        await _serve_lsp_client(reader, writer)
    except Stop:
        logger.info("LSP client disconnecting")
    except Exception:
        logger.exception("Unhandled LSP server error")


async def _serve_lsp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    cli = LspClient()

    while True:
        headers = await read_headers(reader)

        try:
            content_length = int(headers[b"Content-Length"])
        except KeyError:
            logger.warning("No 'Content-Length' header in the message")
            raise Stop from None
        except ValueError:
            logger.warning(
                "Invalid 'Content-Length' header: %.500r",
                headers[b"Content-Length"],
            )
            raise Stop from None

        if not 0 < content_length < MAX_RPC_MESSAGE_LENGTH:
            logger.warning(
                "'Content-Length' is out of reasonable range: %d", content_length
            )
            raise Stop

        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError:
            logger.info(
                "Client abruptly disconnected before we received the whole message"
            )
            raise Stop from None

        try:
            req_payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Client message JSON parse error: %.500r", body, exc_info=True)
            await write_response(
                writer,
                lsp.ResponseErrorMessage(
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.ParseError,
                        message="Could not parse the request as JSON",
                    )
                ),
            )
            continue

        if not isinstance(req_payload, dict):
            logger.warning(
                "Malformed client input (not a dict at top level): %.500r", body
            )
            await write_response(
                writer,
                lsp.ResponseErrorMessage(
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.InvalidRequest,
                        message="Bad request shape (expected a dict at top level)",
                    )
                ),
            )
            continue

        if "method" not in req_payload:
            logger.error("We cannot serve client responses yet: %.500r", body)
            continue

        # This is request or notification
        logger.info(
            "<-- #%s '%s': %r",
            req_payload.get("id", "-"),
            req_payload["method"],
            body,
        )

        try:
            req_cls, resp_cls, _params_cls, _reg_opts = lsp.METHOD_TO_TYPES[
                req_payload["method"]
            ]
        except KeyError:
            logger.warning("Unrecognized LSP request method: %s", req_payload["method"])
            await write_response(
                writer,
                lsp.ResponseErrorMessage(
                    id=req_payload.get("id"),
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.MethodNotFound,
                        message=f"Unknown method: '{req_payload['method']}'",
                    ),
                ),
            )
            continue

        try:
            req = lsp_converter.structure(req_payload, req_cls)
        except Exception:
            logger.warning("Could not parse a request: %.500r", body)
            await write_response(
                writer,
                lsp.ResponseErrorMessage(
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.InvalidRequest,
                        message=f"Invalid request schema for method '{req_payload['method']}'",
                    )
                ),
            )
            continue

        if not resp_cls:
            handle_notification(cli, req.method, req.params)
            continue

        # This is a request -> needs response
        req = cast("lsp.REQUESTS", req)
        result = handle_request(cli, req.method, req.params)
        await write_response(
            writer, resp_cls(id=req.id, result=result), method=req.method
        )


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
            logger.warning("Failed to parse LSP client header: %.500r", line)
            raise Stop

        header, value = mres.groups()
        headers[header] = value

    return headers


async def write_response(
    writer: asyncio.StreamWriter,
    resp: lsp.RESPONSES | lsp.ResponseErrorMessage,
    method: str = "?",
):
    payload = lsp_converter.unstructure(resp)
    raw = json.dumps(payload).encode()

    logger.info("--> #%s '%s': %r", resp.id, method, raw)

    writer.write(b"Content-Length: %d\r\n\r\n" % (len(raw),))
    writer.write(raw)
    await writer.drain()


class Stop(Exception):
    pass


def handle_request(cli: LspClient, method: str, params):
    if method == lsp.INITIALIZE:
        params = cast("lsp.InitializeParams", params)
        cli.name = params.client_info.name if params.client_info else "<Unnamed client>"

        return lsp.InitializeResult(
            server_info=lsp.ServerInfo(name="Dyrel", version="0.1"),
            capabilities=lsp.ServerCapabilities(
                position_encoding=lsp.PositionEncodingKind.Utf16,
                # position_encoding="utf-16",
            ),
        )

    if method == lsp.SET_TRACE:
        return

    logger.error("Unhandled request or notification method: %s", method)
    raise Stop


def handle_notification(cli: LspClient, method: str, params):
    if method == lsp.INITIALIZED:
        return


# @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
# def hover(ls: LanguageServer, params: lsp.HoverParams) -> lsp.Hover:
#     return lsp.Hover(
#         contents=lsp.MarkupContent(
#             kind=lsp.MarkupKind.PlainText,
#             value=f"Dyrel: {list(ls.workspace.text_documents)}",
#         )
#     )
