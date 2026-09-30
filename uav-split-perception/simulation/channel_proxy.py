"""Asynchronous Real-Time 5G Channel Proxy Server & Client.

Replays 3GPP 5G channel trace profiles synchronized to wall-clock time.
Broadcasts channel state at 100 Hz over ZeroMQ PUB socket (IPC/TCP).
Provides high-performance, thread-safe ChannelProxyClient for edge runtimes.
"""

import argparse
import csv
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import zmq

from utils.logger import get_logger

logger = get_logger("ChannelProxy")

DEFAULT_IPC_ENDPOINT = "ipc:///tmp/aegis_channel_proxy.ipc"
DEFAULT_TCP_ENDPOINT = "tcp://127.0.0.1:5570"


def load_trace_csv(filepath: Path) -> List[Dict[str, float]]:
    """Loads a trace CSV into memory."""
    if not filepath.exists():
        raise FileNotFoundError(f"Channel trace file not found: {filepath}")

    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "timestamp_ms": float(row["timestamp_ms"]),
                "sinr_db": float(row["sinr_db"]),
                "bandwidth_mbps": float(row["bandwidth_mbps"]),
                "delay_ms": float(row["delay_ms"]),
                "packet_loss_pct": float(row.get("packet_loss_pct", 0.0)),
            })
    return records


class ChannelProxy:
    """Asynchronous 5G Channel Proxy Server.

    Replays trace states synchronized to wall-clock time and broadcasts over ZeroMQ.
    """

    def __init__(
        self,
        trace_path: str,
        endpoint: Optional[str] = None,
        speed_multiplier: float = 1.0,
        loop: bool = True,
    ):
        self.trace_path = Path(trace_path)
        self.records = load_trace_csv(self.trace_path)
        self.num_records = len(self.records)
        self.speed_multiplier = max(0.1, speed_multiplier)
        self.loop = loop

        # Determine endpoint (IPC default, TCP fallback)
        if endpoint:
            self.endpoint = endpoint
        elif os.name != "nt":
            self.endpoint = DEFAULT_IPC_ENDPOINT
        else:
            self.endpoint = DEFAULT_TCP_ENDPOINT

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.SNDHWM, 100)
        self.socket.bind(self.endpoint)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_state: Dict[str, float] = self.records[0].copy()
        self._lock = threading.Lock()

        logger.info(
            f"ChannelProxy initialized: trace={self.trace_path.name} "
            f"({self.num_records} samples, {self.num_records/100:.1f}s), "
            f"endpoint={self.endpoint}, speed={self.speed_multiplier}x"
        )

    def get_current_state(self) -> Dict[str, float]:
        """Returns the most recent channel state in a thread-safe manner."""
        with self._lock:
            return self._current_state.copy()

    def start(self) -> None:
        """Starts the replayer thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ChannelProxy broadcast loop started.")

    def stop(self) -> None:
        """Stops the replayer thread and closes sockets."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.socket.close(linger=0)
        logger.info("ChannelProxy stopped.")

    def _run_loop(self) -> None:
        """Replay loop synchronized to wall-clock time."""
        # Wait slightly for subscribers to connect
        time.sleep(0.05)

        start_wall_t = time.perf_counter()
        trace_duration_ms = self.records[-1]["timestamp_ms"] - self.records[0]["timestamp_ms"]

        while self._running:
            elapsed_wall_ms = (time.perf_counter() - start_wall_t) * 1000.0 * self.speed_multiplier

            if elapsed_wall_ms > trace_duration_ms:
                if self.loop:
                    start_wall_t = time.perf_counter()
                    elapsed_wall_ms = 0.0
                else:
                    break

            # Find matching sample (trace samples are at 10ms intervals)
            idx = int(elapsed_wall_ms / 10.0)
            if idx >= self.num_records:
                idx = self.num_records - 1

            state = self.records[idx].copy()
            state["wall_time_ms"] = round(elapsed_wall_ms, 2)

            with self._lock:
                self._current_state = state

            # Broadcast over ZeroMQ PUB
            msg = json.dumps(state).encode("utf-8")
            try:
                self.socket.send(msg, flags=zmq.NOBLOCK)
            except zmq.ZMQError:
                pass

            # Sleep until next 10ms tick (100 Hz)
            time.sleep(0.008)


class ChannelProxyClient:
    """Thread-safe Client for consuming 5G channel state from ChannelProxy."""

    def __init__(self, endpoint: Optional[str] = None):
        if endpoint:
            self.endpoint = endpoint
        elif os.name != "nt":
            self.endpoint = DEFAULT_IPC_ENDPOINT
        else:
            self.endpoint = DEFAULT_TCP_ENDPOINT

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.RCVHWM, 100)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.connect(self.endpoint)

        self._running = True
        # No channel information until the first message arrives: callers must check "valid".
        self._current_state: Dict[str, Any] = {"valid": False}
        self._last_rx = 0.0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def get_current_channel_state(self, max_age_s: float = 0.5) -> Dict[str, Any]:
        """Latest channel state; ``valid`` is False if nothing (recent) has been received."""
        with self._lock:
            state = self._current_state.copy()
            if state.get("valid") and time.monotonic() - self._last_rx > max_age_s:
                state["valid"] = False
            return state

    def _recv_loop(self) -> None:
        while self._running:
            try:
                msg = self.socket.recv(flags=zmq.NOBLOCK)
                data = json.loads(msg.decode("utf-8"))
                data["valid"] = True
                with self._lock:
                    self._current_state = data
                    self._last_rx = time.monotonic()
            except zmq.Again:
                time.sleep(0.005)
            except (ValueError, UnicodeDecodeError) as e:
                logger.warning(f"Ignoring malformed channel-state message: {e}")
            except zmq.ZMQError as e:
                if self._running:
                    logger.error(f"Channel-state receiver stopped: {e}")
                break

    def close(self) -> None:
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self.socket.close(linger=0)


def run_self_test() -> bool:
    """Automated verification test for ChannelProxy and ChannelProxyClient."""
    logger.info("Executing ChannelProxy automated self-test...")
    test_trace = Path(__file__).resolve().parent.parent / "traces" / "trace_5g_good.csv"
    if not test_trace.exists():
        from simulation.trace_generator import generate_all_traces
        generate_all_traces()

    proxy = ChannelProxy(trace_path=str(test_trace), speed_multiplier=2.0)
    proxy.start()

    client = ChannelProxyClient(endpoint=proxy.endpoint)
    time.sleep(0.2)  # Give time for initial packets

    states_collected = []
    for _ in range(15):
        st = client.get_current_channel_state()
        states_collected.append(st)
        time.sleep(0.02)

    client.close()
    proxy.stop()

    assert len(states_collected) >= 10, "Failed to collect sufficient channel states"
    assert states_collected[-1].get("valid"), "No channel state received"
    assert states_collected[-1]["bandwidth_mbps"] >= 0, "Invalid bandwidth value"

    logger.info(f"Self-test PASSED! Final state sample: {states_collected[-1]}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 5G Channel Proxy Service")
    parser.add_argument("--trace", type=str, default=str(Path(__file__).resolve().parent.parent / "traces" / "trace_5g_good.csv"), help="Path to trace CSV")
    parser.add_argument("--endpoint", type=str, default=None, help="ZMQ Endpoint (IPC/TCP)")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier")
    parser.add_argument("--test", action="store_true", help="Run automated self-test")
    args = parser.parse_args()

    if args.test:
        run_self_test()
    else:
        srv = ChannelProxy(trace_path=args.trace, endpoint=args.endpoint, speed_multiplier=args.speed)
        srv.start()
        logger.info("ChannelProxy running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            srv.stop()
