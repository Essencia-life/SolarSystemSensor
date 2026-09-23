from dataclasses import dataclass
from .protocol import frame, parse_frame, ProtocolConfig

@dataclass
class SerialSettings:
    port: str
    baudrate: int=9600
    timeout: float=1.0
    bytesize: int=8
    parity: str='N'
    stopbits: int=1

class SerialTransport:
    """Read-only serial transport; no write/configuration API is exposed."""
    def __init__(self, settings: SerialSettings, serial_obj=None, protocol=ProtocolConfig()):
        self.settings=settings; self.protocol=protocol
        if serial_obj is not None: self._serial=serial_obj
        else:
            try:
                import serial
            except ImportError as e: raise RuntimeError('pyserial is required for serial transport; install requirements.txt') from e
            self._serial=serial.Serial(**settings.__dict__)
    def transact(self, payload: bytes) -> bytes:
        self._serial.write(frame(payload,self.protocol)); return parse_frame(self._serial.read_until(bytes([self.protocol.end])),self.protocol)
