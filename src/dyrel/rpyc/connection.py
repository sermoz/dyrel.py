import threading


class Connection:
    def __init__(self, sock):
        self.sock = sock
        self.recv_lock = threading.RLock()

    def serve_one(self):
        """Serves a single request or reply.

        Note that the dispatching of a request might trigger multiple (nested) requests,
        thus this function may be reentrant.
        """
        with self.recv_lock:
            # TODO serhii: continue here
            pass
        try:
            data = None  # Ensure data is initialized
            data = self._channel.poll(timeout) and self._channel.recv()
        except Exception as exc:
            self._recvlock.release()
            if isinstance(exc, EOFError):
                self.close()  # sends close async request
            raise
        else:
            if data:
                self._dispatch(data)  # Dispatch will unbox, invoke callbacks, etc.
                return True
            else:
                self._recvlock.release()
                return False
        finally:
            with self._recv_event:
                self._recv_event.notify_all()

    def _recv_frame(self):
        header = self.stream.read(self.FRAME_HEADER.size)
        length, compressed = self.FRAME_HEADER.unpack(header)
        data = self.stream.read(length + len(self.FLUSHER))[:-len(self.FLUSHER)]
        if compressed:
            data = zlib.decompress(data)
        return data


def receive_message
