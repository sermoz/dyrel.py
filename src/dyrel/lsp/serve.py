from __future__ import annotations

import asyncio
import json
import logging.config
import re
from typing import cast

import lsprotocol.converters
from lsprotocol import types as lsp

from .client import LspClient
from .exc import CloseClientConnection, LspError
from .method_handler import METHOD_HANDLERS

lsp_converter = lsprotocol.converters.get_converter()


logger = logging.getLogger("dyrel.lsp")


MAX_RPC_MESSAGE_LENGTH: int = 100 << 10


async def run_lsp_server():
    tcp_server = await asyncio.start_server(handle_client_connection, "127.0.0.1", 17017)
    async with tcp_server:
        await tcp_server.serve_forever()


async def handle_client_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    logger.info("New LSP client connected!")

    cli = LspClient(reader, writer)

    try:
        await serve_client(cli)
    except CloseClientConnection:
        logger.info("LSP client '%s' disconnecting", cli.name or "?")
    except Exception:
        logger.exception(
            "Unhandled exception in client '%s', disconnecting", cli.name or "?"
        )


async def serve_client(cli: LspClient):
    while True:
        headers = await read_headers(cli.reader)

        try:
            content_length = int(headers[b"Content-Length"])
        except KeyError:
            logger.warning("No 'Content-Length' header in the message")
            raise CloseClientConnection from None
        except ValueError:
            logger.warning(
                "Invalid 'Content-Length' header: %.500r",
                headers[b"Content-Length"],
            )
            raise CloseClientConnection from None

        if not 0 < content_length < MAX_RPC_MESSAGE_LENGTH:
            logger.warning(
                "'Content-Length' is out of reasonable range: %d", content_length
            )
            raise CloseClientConnection

        try:
            body = await cli.reader.readexactly(content_length)
        except asyncio.IncompleteReadError:
            logger.info(
                "Client abruptly disconnected before we received the whole message"
            )
            raise CloseClientConnection from None

        try:
            req_payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Client message JSON parse error: %.500r", body, exc_info=True)
            await write_response(
                cli.writer,
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
                cli.writer,
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
                cli.writer,
                lsp.ResponseErrorMessage(
                    id=req_payload.get("id"),
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.MethodNotFound,
                        message=f"Unknown method: '{req_payload['method']}'",
                    ),
                ),
                method=req_payload["method"],
            )
            continue

        try:
            req = lsp_converter.structure(req_payload, req_cls)
        except Exception:
            logger.warning("Could not parse a message: %.500r", body)
            await write_response(
                cli.writer,
                lsp.ResponseErrorMessage(
                    id=req_payload.get("id"),
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.InvalidRequest,
                        message=f"Invalid request schema for method '{req_payload['method']}'",
                    ),
                ),
                method=req_payload["method"],
            )
            continue

        if not resp_cls:
            # We currently don't handle any notifications.

            # TODO: remember to handle the case when `not cli.is_initialized`: we should
            # log and ignore this notification.
            continue

        # This is a request -> needs response
        req = cast("lsp.REQUESTS", req)

        if not cli.is_initialized and req.method != lsp.INITIALIZE:
            logger.warning("Request '%s' sent before initialization", req.method)
            await write_response(
                cli.writer,
                lsp.ResponseErrorMessage(
                    id=req.id,
                    error=lsp.ResponseError(
                        code=lsp.ErrorCodes.ServerNotInitialized,
                        message="Server not initialized",
                    ),
                ),
                method=req.method,
            )
            continue

        try:
            if req.method not in METHOD_HANDLERS:
                raise LspError("Cannot handle this method")

            if cli.is_initialized and req.method == lsp.INITIALIZE:
                raise LspError("Server already initialized")

            result = METHOD_HANDLERS[req.method](cli, req.params)
        except LspError as exc:
            resp = lsp.ResponseErrorMessage(
                id=req.id,
                error=lsp.ResponseError(
                    code=lsp.LSPErrorCodes.RequestFailed,
                    message=str(exc),
                ),
            )
        except Exception:
            resp = lsp.ResponseErrorMessage(
                id=req.id,
                error=lsp.ResponseError(
                    code=lsp.ErrorCodes.InternalError,
                    message="Server-side error. Please fix Dyrel!",
                ),
            )
        else:
            resp = resp_cls(id=req.id, result=result)

        await write_response(cli.writer, resp, method=req.method)


RE_HEADER = re.compile(rb"([^:]+?): (.+)\r\n")


async def read_headers(reader: asyncio.StreamReader) -> dict[bytes, bytes]:
    headers = {}

    while True:
        line = await reader.readline()

        if not line.endswith(b"\n"):
            # Client disconnected, possibly mid-header
            raise CloseClientConnection

        if line == b"\r\n":
            break

        mres = re.fullmatch(RE_HEADER, line)

        if mres is None:
            logger.warning("Failed to parse LSP client header: %.500r", line)
            raise CloseClientConnection

        header, value = mres.groups()
        headers[header] = value

    return headers


async def write_response(
    writer: asyncio.StreamWriter,
    resp: lsp.RESPONSES | lsp.ResponseErrorMessage,
    method: str = "?",
):
    raw = json.dumps(lsp_converter.unstructure(resp)).encode()

    logger.info("--> #%s '%s': %r", resp.id, method, raw)

    writer.write(b"Content-Length: %d\r\n\r\n" % (len(raw),))
    writer.write(raw)
    await writer.drain()


# @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
# def hover(ls: LanguageServer, params: lsp.HoverParams) -> lsp.Hover:
#     return lsp.Hover(
#         contents=lsp.MarkupContent(
#             kind=lsp.MarkupKind.PlainText,
#             value=f"Dyrel: {list(ls.workspace.text_documents)}",
#         )
#     )
