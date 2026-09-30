"""High-Performance ZeroMQ Inter-Process Communication (IPC) Transport Layer.

Implements memory-guarded ZeroMQ PUSH/PULL and PUB/SUB abstractions
for streaming split-computing activation frames over IPC (ipc://) and TCP (tcp://).
"""

import time
from typing import Optional, Union

import zmq

from utils.logger import get_logger

logger = get_logger("ZMQTransport")

DEFAULT_HWM = 10
DEFAULT_BUFFER_SIZE = 16 * 1024 * 1024  # 16 MB socket send/receive buffer
DEFAULT_TIMEOUT_MS = 1000  # 1000 ms receive timeout
DEFAULT_SEND_TIMEOUT_MS = 5000  # blocking sends give up after 5 s instead of hanging forever
DEFAULT_LINGER_MS = 1000  # time allowed to flush queued frames (incl. the sentinel) on close
DEFAULT_MAX_MSG_BYTES = 64 * 1024 * 1024  # receivers drop anything larger (memory-exhaustion guard)


class AegisZMQPublisher:
    """Edge Transport Node: ZeroMQ Publisher / PUSH socket for streaming wire frames."""

    def __init__(
        self,
        endpoint: str = "ipc:///tmp/aegis_split.ipc",
        socket_type: int = zmq.PUSH,
        bind: bool = True,
        hwm: int = DEFAULT_HWM,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        send_timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ):
        """Initializes ZeroMQ publisher / sender socket.

        Args:
            endpoint: Transport URI (e.g. 'ipc:///tmp/aegis_split.ipc' or 'tcp://127.0.0.1:5555').
            socket_type: ZeroMQ socket pattern (zmq.PUSH or zmq.PUB).
            bind: Whether to bind (True) or connect (False) to the endpoint.
            hwm: High-Water Mark queue limit to prevent unbounded memory growth.
            buffer_size: Kernel socket send buffer size in bytes.
        """
        self.endpoint = endpoint
        self.socket_type = socket_type
        self.bind_mode = bind
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(self.socket_type)

        # Configure socket options
        self.socket.setsockopt(zmq.SNDHWM, hwm)
        self.socket.setsockopt(zmq.SNDBUF, buffer_size)
        self.socket.setsockopt(zmq.SNDTIMEO, send_timeout_ms)
        self.socket.setsockopt(zmq.LINGER, DEFAULT_LINGER_MS)

        if self.bind_mode:
            self.socket.bind(self.endpoint)
            logger.info(f"AegisZMQPublisher bound to endpoint '{self.endpoint}' (HWM={hwm}, SNDBUF={buffer_size / (1024**2):.1f}MB)")
        else:
            self.socket.connect(self.endpoint)
            logger.info(f"AegisZMQPublisher connected to endpoint '{self.endpoint}' (HWM={hwm})")

        self.is_open = True
        self.drop_count = 0
        self.sent_count = 0

    def send_packet(self, packet_bytes: bytes, non_blocking: bool = False) -> bool:
        """Transmits a raw binary packet over the socket.

        Args:
            packet_bytes: Serialized binary wire frame.
            non_blocking: If True, drops packet when queue is full instead of blocking.

        Returns:
            True if packet was sent successfully, False if dropped due to buffer saturation.
        """
        if not self.is_open:
            raise RuntimeError("Cannot send on closed AegisZMQPublisher socket.")

        flags = zmq.NOBLOCK if non_blocking else 0
        try:
            self.socket.send(packet_bytes, flags=flags)
            self.sent_count += 1
            return True
        except zmq.Again:
            self.drop_count += 1
            if self.drop_count == 1 or self.drop_count % 100 == 0:
                logger.warning(
                    f"AegisZMQPublisher queue full or send timed out; frame dropped (total drops: {self.drop_count})"
                )
            return False
        except Exception as e:
            logger.error(f"AegisZMQPublisher send error: {e}")
            raise

    def close(self, linger: int = DEFAULT_LINGER_MS):
        """Closes the socket, allowing up to ``linger`` ms for queued frames to flush."""
        if self.is_open:
            self.is_open = False
            try:
                self.socket.close(linger=linger)
                logger.info(
                    f"AegisZMQPublisher closed. Total Sent: {self.sent_count:,}, Total Drops: {self.drop_count:,}"
                )
            except Exception as e:
                logger.warning(f"Error during AegisZMQPublisher teardown: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AegisZMQSubscriber:
    """Cloud Transport Node: ZeroMQ Subscriber / PULL socket for receiving wire frames."""

    def __init__(
        self,
        endpoint: str = "ipc:///tmp/aegis_split.ipc",
        socket_type: int = zmq.PULL,
        bind: bool = False,
        hwm: int = DEFAULT_HWM,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_msg_bytes: int = DEFAULT_MAX_MSG_BYTES,
    ):
        """Initializes ZeroMQ subscriber / receiver socket.

        Args:
            endpoint: Transport URI.
            socket_type: ZeroMQ socket pattern (zmq.PULL or zmq.SUB).
            bind: Whether to bind (True) or connect (False) to the endpoint.
            hwm: High-Water Mark queue limit.
            buffer_size: Kernel socket receive buffer size in bytes.
            timeout_ms: Receive timeout in milliseconds.
        """
        self.endpoint = endpoint
        self.socket_type = socket_type
        self.bind_mode = bind
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(self.socket_type)

        # Configure socket options
        self.socket.setsockopt(zmq.MAXMSGSIZE, max_msg_bytes)
        self.socket.setsockopt(zmq.RCVHWM, hwm)
        self.socket.setsockopt(zmq.RCVBUF, buffer_size)
        self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self.socket.setsockopt(zmq.LINGER, 0)

        if self.socket_type == zmq.SUB:
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

        if self.bind_mode:
            self.socket.bind(self.endpoint)
            logger.info(f"AegisZMQSubscriber bound to endpoint '{self.endpoint}' (Timeout={timeout_ms}ms)")
        else:
            self.socket.connect(self.endpoint)
            logger.info(f"AegisZMQSubscriber connected to endpoint '{self.endpoint}' (Timeout={timeout_ms}ms)")

        self.is_open = True
        self.recv_count = 0

    def recv_packet(self) -> Optional[bytes]:
        """Receives a raw binary wire packet.

        Returns:
            bytes packet if received, or None if timeout elapsed.
        """
        if not self.is_open:
            raise RuntimeError("Cannot receive on closed AegisZMQSubscriber socket.")

        try:
            packet_bytes = self.socket.recv()
            self.recv_count += 1
            return packet_bytes
        except zmq.Again:
            return None
        except Exception as e:
            logger.error(f"AegisZMQSubscriber receive error: {e}")
            raise

    def close(self, linger: int = 0):
        """Closes the receiving socket (the shared context stays alive for other sockets)."""
        if self.is_open:
            self.is_open = False
            try:
                self.socket.close(linger=linger)
                logger.info(f"AegisZMQSubscriber closed. Total Received: {self.recv_count:,}")
            except Exception as e:
                logger.warning(f"Error during AegisZMQSubscriber teardown: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
