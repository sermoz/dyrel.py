"""Standalone process hosting the Dyrel engine.

Included:
    - standalone process embedding Dyrel;
    - watching a directory with relational modules and reloading changed files;
    - an LSP server (implemented in the `dyrel.lsp` package).

This is needed mainly as a tool for experimenting, testing and prototyping with Dyrel. In
contrast, normally Dyrel is expected to be included/embedded in user-controlled
applications such as a FastAPI web server or a PyGTK GUI application.
"""
