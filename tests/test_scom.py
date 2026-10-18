import struct

import pytest

from studer_sensor.scom import (
    ScomError, ScomFrameError, ScomReader, ScomTimeout, Frame, build_frame, checksum,
    decode_value, device_label, parse_frame, parse_queries, parse_read_property_response,
    read_property_request,
)
from studer_sensor.config import ServiceConfig
from studer_sensor.telemetry import Collector
from studer_sensor.transport import SerialSettings, ScomTransport

# Spec chapter 5.2: read user info 3000 (battery voltage) from the first Xtender.
SPEC_REQUEST = bytes.fromhex("AA 00 01 00 00 00 65 00 00 00 0A 00 6F 71 "
                             "00 01 01 00 B8 0B 00 00 01 00 C5 90")
SPEC_RESPONSE = bytes.fromhex("AA 00 65 00 00 00 01 00 00 00 0E 00 73 09 "
                              "02 01 01 00 B8 0B 00 00 01 00 00 A0 BB 41 63 57")


def battery_request():
    return build_frame(1, 101, read_property_request(1, 3000, 1))


def test_request_matches_spec_example_byte_for_byte():
    assert battery_request() == SPEC_REQUEST


def test_checksum_matches_spec_values():
    assert checksum(SPEC_REQUEST[1:12]) == bytes.fromhex("6F 71")
    assert checksum(SPEC_REQUEST[14:24]) == bytes.fromhex("C5 90")
    assert checksum(SPEC_RESPONSE[1:12]) == bytes.fromhex("73 09")
    assert checksum(SPEC_RESPONSE[14:28]) == bytes.fromhex("63 57")


def test_response_decodes_to_spec_value():
    frame = parse_frame(SPEC_RESPONSE)
    assert (frame.src, frame.dst) == (101, 1)
    payload = parse_read_property_response(frame, 1, 3000, 1)
    assert decode_value("FLOAT", payload) == 23.453125


def test_frame_rejects_bad_checksums_and_markers():
    for index in (0, 13, 14, -1):
        broken = bytearray(SPEC_RESPONSE)
        broken[index] ^= 0xFF
        with pytest.raises(ScomFrameError):
            parse_frame(bytes(broken))
    with pytest.raises(ScomFrameError):
        parse_frame(SPEC_RESPONSE[:-1])


def test_device_error_raises_with_name():
    data = struct.pack("<BBHIHH", 0x03, 0x01, 1, 3000, 1, 0x0022)
    frame = Frame(src=101, dst=1, data=data)
    with pytest.raises(ScomError) as exc:
        parse_read_property_response(frame, 1, 3000, 1)
    assert exc.value.code == 0x0022 and exc.value.name == "OBJECT_ID_NOT_FOUND"


def test_response_for_other_object_is_rejected():
    frame = parse_frame(SPEC_RESPONSE)
    with pytest.raises(ScomFrameError):
        parse_read_property_response(frame, 1, 3005, 1)


def test_decode_enum_and_length_check():
    assert decode_value("ENUM", b"\x04\x00") == 4
    with pytest.raises(ScomFrameError):
        decode_value("FLOAT", b"\x00\x00")


def test_parse_queries_default_and_custom():
    default = parse_queries(None)
    assert default[0].metric == "xt1_battery_voltage_v" and default[0].unit == "V"
    custom = parse_queries("601:7002, 301:11004, 101:3010")
    assert [q.metric for q in custom] == ["bsp_state_of_charge_pct", "vt1_pv_power_w",
                                          "xt1_battery_cycle_phase"]
    assert custom[2].fmt == "ENUM"
    assert parse_queries("101:9999")[0].metric == "xt1_info_9999"
    with pytest.raises(ValueError):
        parse_queries("101")


def test_device_labels():
    assert [device_label(a) for a in (101, 109, 192, 301, 601, 701, 702, 999)] == [
        "xt1", "xt9", "xt_l2", "vt1", "bsp", "vs1", "vs2", "dev999"]


class FakeTransport:
    """Answers each request with a float, an error or a timeout, one request at a time."""
    def __init__(self, answers):
        self.answers, self.sent = answers, []

    def request(self, raw):
        self.sent.append(raw)
        answer = self.answers[len(self.sent) - 1]
        if answer == "timeout":
            raise ScomTimeout("no answer")
        info_id = struct.unpack("<I", raw[14 + 4:14 + 8])[0]
        if isinstance(answer, int):
            data = struct.pack("<BBHIHH", 0x03, 0x01, 1, info_id, 1, answer)
        else:
            data = struct.pack("<BBHIHf", 0x02, 0x01, 1, info_id, 1, answer)
        return Frame(src=101, dst=1, data=data)


def test_reader_sends_one_request_per_info_and_skips_failures():
    transport = FakeTransport([12.5, "timeout", 0x0002])
    reader = ScomReader(transport, parse_queries("101:3000,101:3005,601:7002"))
    assert reader() == {"xt1_battery_voltage_v": 12.5}
    assert len(transport.sent) == 3
    assert transport.sent[0] == build_frame(1, 101, read_property_request(1, 3000, 1))
    assert transport.sent[2] == build_frame(1, 601, read_property_request(1, 7002, 1))


def test_reader_raises_when_everything_fails():
    reader = ScomReader(FakeTransport(["timeout"]), parse_queries("101:3000"))
    with pytest.raises(RuntimeError):
        reader()


def test_reader_feeds_collector_with_units():
    reader = ScomReader(FakeTransport([51.25]), parse_queries("101:3000"))
    assert Collector(reader, reader.definitions()).collect() == {
        "xt1_battery_voltage_v": {"value": 51.25, "unit": "V"}}


class FakeSerial:
    def __init__(self, reply):
        self.reply, self.pos, self.sent, self.reset = reply, 0, b"", False

    def reset_input_buffer(self): self.reset = True
    def write(self, data): self.sent += data

    def read(self, size):
        chunk = self.reply[self.pos:self.pos + size]
        self.pos += size
        return chunk


def test_scom_transport_roundtrip_with_spec_frames():
    serial = FakeSerial(SPEC_RESPONSE)
    frame = ScomTransport(SerialSettings("/dev/null"), serial).request(SPEC_REQUEST)
    assert serial.sent == SPEC_REQUEST and serial.reset
    assert decode_value("FLOAT", parse_read_property_response(frame, 1, 3000, 1)) == 23.453125


def test_scom_transport_times_out_on_short_reply():
    serial = FakeSerial(SPEC_RESPONSE[:10])
    with pytest.raises(ScomTimeout):
        ScomTransport(SerialSettings("/dev/null"), serial).request(SPEC_REQUEST)


def test_serial_defaults_follow_spec():
    settings = SerialSettings("/dev/null")
    assert (settings.baudrate, settings.parity, settings.bytesize, settings.stopbits) == (
        38400, "E", 8, 1)
    cfg = ServiceConfig.from_env({"SERIAL_PORT": "p", "DATAHUB_URL": "u",
                                  "DATAHUB_API_KEY": "k", "DEVICE_ID": "d"})
    assert (cfg.serial_baudrate, cfg.serial_parity, cfg.scom_src_addr) == (38400, "E", 1)
    assert cfg.scom_infos is None


def test_metric_names_follow_datahub_convention():
    names = [q.metric for q in parse_queries("101:3000,101:3081,601:7002,101:3028")]
    assert names == ["xt1_battery_voltage_v", "xt1_energy_from_today_kwh",
                     "bsp_state_of_charge_pct", "xt1_operating_state"]


def test_variostring_infos_use_vs_address_and_watts():
    names = {q.info_id: q for q in parse_queries("701:15004,701:15010,701:15017,701:15108")}
    assert names[15004].metric == "vs1_pv_voltage_v"
    assert names[15010].metric == "vs1_pv_power_w" and names[15010].scale == 1000.0
    assert names[15017].metric == "vs1_production_kwh_today_kwh"
    assert names[15108].metric == "vs1_state" and names[15108].fmt == "ENUM"


def test_kw_values_are_reported_in_watts():
    reader = ScomReader(FakeTransport([4.2]), parse_queries("701:15010"))
    result = Collector(reader, reader.definitions()).collect()
    assert result == {"vs1_pv_power_w": {"value": pytest.approx(4200.0), "unit": "W"}}


def test_nan_values_are_skipped_not_sent():
    # BSP remaining autonomy is NaN while charging; NaN is not valid JSON for the DataHub.
    reader = ScomReader(FakeTransport([float("nan"), 12.5]), parse_queries("601:7004,101:3000"))
    assert reader() == {"xt1_battery_voltage_v": 12.5}


def test_catalog_units_match_appendix():
    queries = {q.info_id: q for q in parse_queries("601:7004,101:3136,601:7005")}
    assert queries[7004].unit == "min" and queries[7004].metric == "bsp_remaining_autonomy_min"
    assert queries[3136].unit == "W" and queries[3136].scale == 1000.0
    assert queries[7005].metric == "bsp_temperature_c"
