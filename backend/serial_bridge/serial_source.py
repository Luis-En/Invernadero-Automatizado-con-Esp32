"""Asynchronous reader for the gateway's serial line protocol.

pyserial is blocking, so the reader runs in its own thread and hands parsed
messages to the asyncio loop through a queue. The thread reconnects on its own
if the gateway is unplugged and replugged.
"""

import asyncio
import logging
import threading
import time
from typing import AsyncIterator, Optional

import serial

from gateway_protocol import MAX_LINE_BYTES, frame_line, parse_line

logger = logging.getLogger(__name__)

READ_CHUNK_BYTES = 256
QUEUE_MAXSIZE = 1000


class SerialSource:
    def __init__(self, port: str, baudrate: int = 115200, reconnect_delay: float = 5.0):
        self._port = port
        self._baudrate = baudrate
        self._reconnect_delay = reconnect_delay
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._serial = None
        self._serial_lock = threading.Lock()

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(target=self._reader_thread, name="serial-reader", daemon=True)
        self._thread.start()

    async def wait_open(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._serial_lock:
                if self._serial is not None:
                    return True
            await asyncio.sleep(0.1)
        return False

    async def messages(self) -> AsyncIterator[dict]:
        try:
            while True:
                message = await self._queue.get()
                if message is None:
                    break
                yield message
        finally:
            self._stop.set()
            self._close_serial()

    def write_json(self, message: dict) -> bool:
        with self._serial_lock:
            port = self._serial
            if port is None:
                return False
            try:
                port.write(frame_line(message))
                return True
            except (serial.SerialException, OSError) as exc:
                logger.warning("serial write failed: %s", exc)
                return False

    def _reader_thread(self) -> None:
        while not self._stop.is_set():
            try:
                with serial.Serial(self._port, self._baudrate, timeout=1) as port:
                    logger.info("gateway connected on %s @ %d baud", self._port, self._baudrate)
                    with self._serial_lock:
                        self._serial = port
                    self._read_lines(port)
            except (serial.SerialException, OSError) as exc:
                logger.warning("serial port %s unavailable: %s", self._port, exc)
                self._stop.wait(self._reconnect_delay)
            finally:
                with self._serial_lock:
                    self._serial = None

    def _read_lines(self, port: serial.Serial) -> None:
        buffer = b""
        while not self._stop.is_set():
            try:
                chunk = port.read(READ_CHUNK_BYTES)
            except (serial.SerialException, OSError) as exc:
                logger.warning("serial read failed: %s", exc)
                return
            if not chunk:
                continue

            buffer += chunk
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                message = parse_line(line)
                if message is not None:
                    self._enqueue(message)

            if len(buffer) > MAX_LINE_BYTES:
                logger.warning("serial line exceeded %d bytes, discarding", MAX_LINE_BYTES)
                buffer = b""

    def _enqueue(self, message: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def _put() -> None:
            try:
                self._queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("serial queue full, dropping %s", message.get("type"))

        loop.call_soon_threadsafe(_put)

    def _close_serial(self) -> None:
        with self._serial_lock:
            port = self._serial
            self._serial = None
        if port is not None:
            try:
                port.close()
            except (serial.SerialException, OSError):
                pass
