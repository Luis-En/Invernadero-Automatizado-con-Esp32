"""Framing and checksum helpers for the ESP32 gateway serial protocol.

The gateway emits one message per line:

    <json>*<CRC16 hex>\n

CRC16 is CRC-16/CCITT-FALSE (poly 0x1021, init 0x0000), matching the firmware
and Python's ``binascii.crc_hqx(data, 0)``. The checksum covers the JSON bytes
only, not the separator, the hex digits or the newline.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_LINE_BYTES = 8192


def crc16_ccitt(data: bytes) -> int:
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def frame_line(message: dict) -> bytes:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    return payload + b"*%04X\n" % crc16_ccitt(payload)


def parse_line(raw: bytes) -> Optional[dict]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return None

    # Firmware debug/comment lines start with '#'. They are human-readable and
    # intentionally not framed, so skip them silently instead of warning.
    if text.startswith("#"):
        logger.debug("gateway comment: %s", text)
        return None

    if "*" in text:
        payload, _, crc_text = text.rpartition("*")
        try:
            expected = int(crc_text, 16)
        except ValueError:
            logger.warning("gateway line has malformed checksum: %r", text[:80])
            return None
        if crc16_ccitt(payload.encode("utf-8")) != expected:
            logger.warning("gateway line checksum mismatch, dropping: %r", payload[:80])
            return None
        text = payload

    try:
        message = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("gateway line is not JSON: %r", text[:80])
        return None

    if not isinstance(message, dict):
        return None
    return message
