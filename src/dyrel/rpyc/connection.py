import threading
import struct


class Connection:
    def __init__(self, sock):
        self.sock = sock

    def serve_one(self):
        """Serves a single message (request or reply).

        Note that the dispatching of a request might trigger multiple (nested) requests,
        thus this function may be reentrant.
        """
        data = self._recv_frame()
        self._dispatch(data)

    def _recv_frame(self) -> bytes:
        buf = self.sock.recv(4)
        if not buf:
            raise RuntimeError("disconnect")

        length = struct.unpack("!I", buf)
        
        buf = self.sock.recv(length)
        if not buf:
            raise RuntimeError("disconnect")

        return buf

    def _dispatch(self, data):  # serving---dispatch?
        # TODO: continue here
        msg, = brine.I1.unpack(data[:1])  # unpack just msg to minimize time to release
        if msg == consts.MSG_REQUEST:
            if self._bind_threads:
                self._get_thread()._occupation_count += 1
            else:
                self._recvlock.release()
            seq, args = brine.load(data[1:])
            self._dispatch_request(seq, args)
        else:
            if self._bind_threads:
                this_thread = self._get_thread()
                this_thread._occupation_count -= 1
                if this_thread._occupation_count == 0:
                    this_thread._remote_thread_id = UNBOUND_THREAD_ID
            if msg == consts.MSG_REPLY:
                seq, args = brine.load(data[1:])
                obj = self._unbox(args)
                self._seq_request_callback(msg, seq, False, obj)
                if not self._bind_threads:
                    self._recvlock.release()  # releasing here fixes race condition with AsyncResult.wait
            elif msg == consts.MSG_EXCEPTION:
                if not self._bind_threads:
                    self._recvlock.release()
                seq, args = brine.load(data[1:])
                obj = self._unbox_exc(args)
                self._seq_request_callback(msg, seq, True, obj)
            else:
                raise ValueError(f"invalid message type: {msg!r}")
