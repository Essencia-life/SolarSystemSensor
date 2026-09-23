"""Framing primitives. Device command constants intentionally not guessed."""
from dataclasses import dataclass

# Generic framing examples only; these are not verified Studer defaults.
# Always construct ProtocolConfig from the official protocol specification.
START_BYTE = 0x02
END_BYTE = 0x03
@dataclass(frozen=True)
class ProtocolConfig:
    start: int = START_BYTE
    end: int = END_BYTE
    checksum: str = 'mod256'

def checksum(data: bytes) -> int: return sum(data) & 0xff

def frame(payload: bytes, config=ProtocolConfig()) -> bytes:
    return bytes([config.start])+payload+bytes([checksum(payload), config.end])

def parse_frame(data: bytes, config=ProtocolConfig()) -> bytes:
    if len(data)<4 or data[0]!=config.start or data[-1]!=config.end: raise ValueError('invalid frame markers')
    payload=data[1:-2]
    if data[-2] != checksum(payload): raise ValueError('checksum mismatch')
    return payload
