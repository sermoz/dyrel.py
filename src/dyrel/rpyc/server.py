from __future__ import annotations

import socket
import threading


class Server:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    def _serve_forever(self):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(self.socket_path)

        while True:
            client, address = listener.accept()
            

    
    @classmethod
    def serve_forever(cls, socket_path: str) -> Server:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(socket_path)

        return Server(listener)
