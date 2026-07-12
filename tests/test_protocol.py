import pytest

from app.serial.protocol import BinaryFrameProtocol, BinaryFrameStreamParser, crc16_modbus


def test_known_modbus_crc():
    assert crc16_modbus(b"123456789") == 0x4B37


def test_protocol_round_trip():
    protocol = BinaryFrameProtocol()
    encoded = protocol.encode(7, b"abc")
    assert protocol.decode(encoded).command == 7
    assert protocol.decode(encoded).payload == b"abc"


def test_protocol_rejects_corrupt_crc():
    encoded = bytearray(BinaryFrameProtocol().encode(1, b"x"))
    encoded[-1] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        BinaryFrameProtocol().decode(bytes(encoded))


def test_stream_parser_handles_noise_partial_and_multiple_packets():
    protocol = BinaryFrameProtocol()
    parser = BinaryFrameStreamParser()
    first = protocol.encode(1, b"one")
    second = protocol.encode(2, b"two")
    assert parser.feed(b"noise" + first[:4]) == []
    frames = parser.feed(first[4:] + second)
    assert [(frame.command, frame.payload) for frame in frames] == [(1, b"one"), (2, b"two")]


def test_stream_parser_recovers_after_bad_crc():
    protocol = BinaryFrameProtocol()
    parser = BinaryFrameStreamParser()
    bad = bytearray(protocol.encode(1, b"bad"))
    bad[-1] ^= 1
    frames = parser.feed(bytes(bad) + protocol.encode(2, b"ok"))
    assert [(frame.command, frame.payload) for frame in frames] == [(2, b"ok")]
