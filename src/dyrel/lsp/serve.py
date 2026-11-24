from __future__ import annotations

import asyncio
import json
import logging.config
import re
from typing import cast

import lsprotocol.converters
from lsprotocol import types as lsp

lsp_converter = lsprotocol.converters.get_converter()


logger = logging.getLogger("dyrel.lsp")


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
    while True:
        headers = await read_headers(reader)

        try:
            content_length = int(headers[b"Content-Length"])
        except KeyError:
            logger.warning("No 'Content-Length' header in the message")
            raise Stop from None
        except ValueError:
            logger.warning(
                "Invalid 'Content-Length' header: %.300r",
                headers[b"Content-Length"],
            )
            raise Stop from None

        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError:
            logger.info("Could not read the whole message from the client, quitting")
            raise Stop from None

        req_payload = json.loads(body)

        if not isinstance(req_payload, dict):
            logger.warning("Malformed client input: %.300r", req_payload)
            raise Stop from None

        if "method" in req_payload:
            # This is request or notification
            logger.info(
                "<-- #%s '%s': %.300r",
                req_payload.get("id", "-"),
                req_payload["method"],
                req_payload,
            )

            try:
                req_cls, resp_cls, _params_cls, _reg_opts = lsp.METHOD_TO_TYPES[
                    req_payload["method"]
                ]
            except KeyError:
                logger.warning(
                    "Unrecognized LSP request method: %s", req_payload["method"]
                )
                raise Stop from None

            try:
                req = lsp_converter.structure(req_payload, req_cls)
            except Exception:
                logger.warning("Could not parse a request: %.500r", req_payload)
                raise Stop from None

            result = handle_client_message(req.method, req.params)

            if resp_cls:
                # This is a request -> needs response
                req = cast("lsp.REQUESTS", req)
                resp = resp_cls(
                    jsonrpc="2.0",
                    id=req.id,
                    result=result,
                )

                try:
                    resp_payload = lsp_converter.unstructure(resp)
                except Exception:
                    logger.exception(
                        "Could not unstructure our response for '%s': %r",
                        req.method,
                        resp,
                    )
                    raise Stop from None

                logger.info("--> #%s '%s': %.300r", req.id, req.method, resp_payload)
                await write_payload(writer, resp_payload)
            else:
                assert result is None, "Returned a result for notification"

            # if resp:
            #     if not resp_cls:
            #         logger.error(
            #             "We attempted to return a response for notification (%s)",
            #             payload["method"],
            #         )
            #         raise Stop

        else:
            logger.error("We cannot serve client requests yet: %.300r", req_payload)
            raise Stop


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
            logger.warning("Failed to parse LSP client header: %.300r", line)
            raise Stop

        header, value = mres.groups()
        headers[header] = value

    return headers


async def write_payload(writer: asyncio.StreamWriter, payload):
    raw = json.dumps(payload).encode()
    writer.write(b"Content-Length: %d\r\n\r\n" % (len(raw),))
    writer.write(raw)
    await writer.drain()


class Stop(Exception):
    pass


def handle_client_message(method: str, params):
    if method == "initialize":
        return handle_initialize(params)
    elif method == "initialized":
        return handle_initialized(params)
    else:
        logger.error("Unhandled request or notification method: %s", method)
        raise Stop


def handle_initialize(params: lsp.InitializeParams) -> lsp.InitializeResult:
    logger.info("Client initializing: %r", params.client_info)
    return lsp.InitializeResult(
        server_info=lsp.ServerInfo(name="Dyrel", version="0.1"),
        capabilities=lsp.ServerCapabilities(
            position_encoding=lsp.PositionEncodingKind.Utf16,
            # position_encoding="utf-16",
        ),
    )


def handle_initialized(params: lsp.InitializedParams):
    logger.info("Initialized is received!")


# @lsp_server.feature(lsp.TEXT_DOCUMENT_HOVER)
# def hover(ls: LanguageServer, params: lsp.HoverParams) -> lsp.Hover:
#     return lsp.Hover(
#         contents=lsp.MarkupContent(
#             kind=lsp.MarkupKind.PlainText,
#             value=f"Dyrel: {list(ls.workspace.text_documents)}",
#         )
#     )
