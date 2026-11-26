from __future__ import annotations


class CloseClientConnection(Exception):
    """Helper exception class: raise to close connection with this LSP client.

    Supposed to be used in unrecoverable error situations.
    """


class LspError(Exception):
    pass
