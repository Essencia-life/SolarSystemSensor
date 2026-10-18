"""Studer SCOM framing for the Xcom-232i, read-only.

Implements the data link layer (chapter 3) and the READ_PROPERTY service
(chapter 4.2.1) of "Technical specification - Xtender serial protocol V1.5.16"
(docs/). There is deliberately no WRITE_PROPERTY helper.

One READ_PROPERTY request reads exactly one property of one object; the
protocol has no bulk read, so every value is its own request/response pair.
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

from .telemetry import MetricDefinition

START_BYTE = 0xAA
HEADER_LEN = 14          # start, flags, src(4), dst(4), length(2), header checksum(2)
CHECKSUM_LEN = 2
MAX_DATA_LEN = 240

SERVICE_READ_PROPERTY = 0x01
OBJECT_USER_INFO = 0x0001
PROPERTY_INFO_VALUE = 0x0001

FLAG_ERROR = 0x01
FLAG_RESPONSE = 0x02

ERROR_NAMES = {
    0x0001: "INVALID_FRAME", 0x0002: "DEVICE_NOT_FOUND", 0x0003: "RESPONSE_TIMEOUT",
    0x0011: "SERVICE_NOT_SUPPORTED", 0x0012: "INVALID_SERVICE_ARGUMENT",
    0x0013: "SCOM_ERROR_GATEWAY_BUSY", 0x0021: "TYPE_NOT_SUPPORTED",
    0x0022: "OBJECT_ID_NOT_FOUND", 0x0023: "PROPERTY_NOT_SUPPORTED",
    0x0024: "INVALID_DATA_LENGTH", 0x0025: "PROPERTY_IS_READ_ONLY", 0x0026: "INVALID_DATA",
    0x0027: "DATA_TOO_SMALL", 0x0028: "DATA_TOO_BIG", 0x0029: "WRITE_PROPERTY_FAILED",
    0x002A: "READ_PROPERTY_FAILED", 0x002B: "ACCESS_DENIED",
    0x002C: "SCOM_ERROR_OBJECT_NOT_SUPPORTED",
    0x002D: "SCOM_ERROR_MULTICAST_READ_NOT_SUPPORTED", 0x0081: "INVALID_SHELL_ARG",
}


class ScomFrameError(ValueError):
    """Malformed frame: bad start byte, checksum, length or unexpected response."""


class ScomTimeout(TimeoutError):
    """The Xcom-232i did not answer in time (spec: up to 2 s)."""


class ScomError(Exception):
    """The device answered with an error code (spec chapter 4.3)."""

    def __init__(self, code: int):
        self.code = code
        self.name = ERROR_NAMES.get(code, f"0x{code:04X}")
        super().__init__(f"SCOM error {self.name} (0x{code:04X})")


def checksum(data: bytes) -> bytes:
    """Spec 3.4: A starts at 0xFF, B at 0, both mod 256; returns bytes [A, B]."""
    a, b = 0xFF, 0
    for byte in data:
        a = (a + byte) & 0xFF
        b = (b + a) & 0xFF
    return bytes((a, b))


@dataclass(frozen=True)
class Frame:
    src: int
    dst: int
    data: bytes
    flags: int = 0


def build_frame(src: int, dst: int, data: bytes, flags: int = 0) -> bytes:
    if len(data) > MAX_DATA_LEN:
        raise ValueError(f"frame data too long: {len(data)} > {MAX_DATA_LEN}")
    header = struct.pack("<BIIH", flags, src, dst, len(data))
    return bytes([START_BYTE]) + header + checksum(header) + data + checksum(data)


def parse_header(header: bytes) -> tuple[int, int, int, int]:
    """Validate the 14 header bytes; returns (flags, src, dst, data_length)."""
    if len(header) != HEADER_LEN:
        raise ScomFrameError(f"header must be {HEADER_LEN} bytes, got {len(header)}")
    if header[0] != START_BYTE:
        raise ScomFrameError(f"bad start byte 0x{header[0]:02X}")
    if checksum(header[1:12]) != header[12:14]:
        raise ScomFrameError("header checksum mismatch")
    flags, src, dst, length = struct.unpack("<BIIH", header[1:12])
    if length > MAX_DATA_LEN:
        raise ScomFrameError(f"data length {length} exceeds {MAX_DATA_LEN}")
    return flags, src, dst, length


def parse_frame(raw: bytes) -> Frame:
    flags, src, dst, length = parse_header(raw[:HEADER_LEN])
    if len(raw) != HEADER_LEN + length + CHECKSUM_LEN:
        raise ScomFrameError("frame length does not match data_length")
    data = raw[HEADER_LEN:HEADER_LEN + length]
    if checksum(data) != raw[-CHECKSUM_LEN:]:
        raise ScomFrameError("data checksum mismatch")
    return Frame(src=src, dst=dst, data=data, flags=flags)


def read_property_request(object_type: int, object_id: int, property_id: int) -> bytes:
    """frame_data of a READ_PROPERTY request (10 bytes, spec 4.2.1)."""
    return struct.pack("<BBHIH", 0x00, SERVICE_READ_PROPERTY, object_type, object_id, property_id)


def parse_read_property_response(frame: Frame, object_type: int, object_id: int,
                                 property_id: int) -> bytes:
    """Return property_data of a successful response, raise ScomError on a device error."""
    data = frame.data
    if len(data) < 10:
        raise ScomFrameError("response too short")
    flags, service, otype, oid, pid = struct.unpack("<BBHIH", data[:10])
    if (not flags & FLAG_RESPONSE or service != SERVICE_READ_PROPERTY
            or (otype, oid, pid) != (object_type, object_id, property_id)):
        raise ScomFrameError("response does not match the request")
    payload = data[10:]
    if flags & FLAG_ERROR:
        if len(payload) < 2:
            raise ScomFrameError("error response without error code")
        raise ScomError(struct.unpack("<H", payload[:2])[0])
    return payload


_FORMATS = {"FLOAT": ("<f", 4), "INT32": ("<i", 4), "ENUM": ("<H", 2), "BOOL": ("<B", 1)}


def decode_value(fmt: str, payload: bytes):
    """Decode property_data (little endian, spec 4.2.3)."""
    try:
        spec, size = _FORMATS[fmt]
    except KeyError:
        raise ValueError(f"unsupported format {fmt!r}") from None
    if len(payload) != size:
        raise ScomFrameError(f"expected {size} bytes for {fmt}, got {len(payload)}")
    return struct.unpack(spec, payload)[0]


@dataclass(frozen=True)
class InfoSpec:
    name: str
    unit: str | None = None
    fmt: str = "FLOAT"


# Curated subset of the user infos in spec chapters 6.2, 6.5 and 6.9.
INFO_CATALOG = {
    3000: InfoSpec("battery_voltage", "V"),
    3005: InfoSpec("battery_charge_current", "A"),
    3007: InfoSpec("state_of_charge", "%"),
    3006: InfoSpec("battery_voltage_ripple", "V"),
    3008: InfoSpec("low_voltage_disconnect", "V"),
    3010: InfoSpec("battery_cycle_phase", None, "ENUM"),
    3011: InfoSpec("input_voltage", "V"),
    3012: InfoSpec("input_current", "A"),
    3018: InfoSpec("input_limit_reached", None, "ENUM"),
    3019: InfoSpec("boost_active", None, "ENUM"),
    3020: InfoSpec("transfer_relay", None, "ENUM"),
    3021: InfoSpec("output_voltage", "V"),
    3022: InfoSpec("output_current", "A"),
    3028: InfoSpec("operating_state", None, "ENUM"),
    3045: InfoSpec("overload_count"),
    3046: InfoSpec("overtemperature_count"),
    3047: InfoSpec("battery_overvoltage_count"),
    3076: InfoSpec("battery_discharge_prev_day", "kWh"),
    3078: InfoSpec("battery_discharge_today", "kWh"),
    3080: InfoSpec("energy_from_prev_day", "kWh"),
    3081: InfoSpec("energy_from_today", "kWh"),
    3082: InfoSpec("consumers_energy_prev_day", "kWh"),
    3083: InfoSpec("consumers_energy_today", "kWh"),
    3084: InfoSpec("input_frequency", "Hz"),
    3085: InfoSpec("output_frequency", "Hz"),
    3087: InfoSpec("output_active_power", "W"),
    3088: InfoSpec("input_active_power", "W"),
    7000: InfoSpec("battery_voltage", "V"),
    7001: InfoSpec("battery_current", "A"),
    7002: InfoSpec("state_of_charge", "%"),
    7003: InfoSpec("power", "W"),
    7004: InfoSpec("remaining_autonomy"),
    7006: InfoSpec("relative_capacity", "%"),
    7029: InfoSpec("battery_temperature", "°C"),
    11000: InfoSpec("battery_voltage", "V"),
    11001: InfoSpec("battery_current", "A"),
    11002: InfoSpec("pv_voltage", "V"),
    11004: InfoSpec("pv_power", "kW"),
    11006: InfoSpec("production_ah_today", "Ah"),
    11007: InfoSpec("production_kwh_today", "kWh"),
    11016: InfoSpec("operating_mode", None, "ENUM"),
}

# First Xtender (address 101): battery, AC input and output.
DEFAULT_QUERIES = "101:3000,101:3005,101:3011,101:3012,101:3021,101:3022,101:3087,101:3088"


# DataHub convention: <name>_<unit>, e.g. battery_voltage_v, battery_soc_pct, pv_power_w.
UNIT_SUFFIX = {"V": "_v", "A": "_a", "%": "_pct", "W": "_w", "kW": "_kw", "Hz": "_hz",
               "°C": "_c", "Ah": "_ah", "kWh": "_kwh"}


def device_label(dst: int) -> str:
    if 101 <= dst <= 109:
        return f"xt{dst - 100}"
    if 191 <= dst <= 193:
        return f"xt_l{dst - 190}"
    if 301 <= dst <= 331:
        return f"vt{dst - 300}"
    return {401: "xcom_ms", 501: "xcom", 601: "bsp"}.get(dst, f"dev{dst}")


@dataclass(frozen=True)
class InfoQuery:
    device: int
    info_id: int
    metric: str
    unit: str | None = None
    fmt: str = "FLOAT"


def parse_queries(spec: str | None) -> list[InfoQuery]:
    """Parse 'dst:info[:FORMAT],...', e.g. '101:3000,601:7002,101:3010:ENUM'."""
    queries = []
    for item in (spec or DEFAULT_QUERIES).split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(f"bad SCOM_INFOS entry {item!r}, expected dst:info[:FORMAT]")
        device, info_id = int(parts[0]), int(parts[1])
        known = INFO_CATALOG.get(info_id, InfoSpec(f"info_{info_id}"))
        fmt = parts[2].upper() if len(parts) == 3 else known.fmt
        if fmt not in _FORMATS:
            raise ValueError(f"unsupported format {fmt!r} in {item!r}")
        queries.append(InfoQuery(device, info_id, f"{device_label(device)}_{known.name}{UNIT_SUFFIX.get(known.unit, '')}",
                                 known.unit, fmt))
    return queries


class ScomReader:
    """Reads each configured info with its own READ_PROPERTY request.

    Failed reads (device missing, timeout, garbled frame) are logged and skipped so
    one absent device does not hide the others; if every read fails it raises.
    """

    def __init__(self, transport, queries, src_addr: int = 1, logger=None):
        self.transport, self.queries, self.src_addr = transport, list(queries), src_addr
        self.log = logger or logging.getLogger(__name__)

    def definitions(self) -> dict:
        return {q.metric: MetricDefinition(q.metric, q.unit) for q in self.queries}

    def read_info(self, query: InfoQuery):
        request = build_frame(self.src_addr, query.device, read_property_request(
            OBJECT_USER_INFO, query.info_id, PROPERTY_INFO_VALUE))
        reply = self.transport.request(request)
        payload = parse_read_property_response(reply, OBJECT_USER_INFO, query.info_id,
                                               PROPERTY_INFO_VALUE)
        return decode_value(query.fmt, payload)

    def __call__(self) -> dict:
        values = {}
        for query in self.queries:
            try:
                values[query.metric] = self.read_info(query)
            except (ScomError, ScomTimeout, ScomFrameError) as exc:
                self.log.warning("SCOM read %s (dst %d, info %d) failed: %s",
                                 query.metric, query.device, query.info_id, exc)
        if self.queries and not values:
            raise RuntimeError("all SCOM reads failed")
        return values
