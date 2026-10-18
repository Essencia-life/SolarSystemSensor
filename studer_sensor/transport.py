from dataclasses import dataclass
from .scom import HEADER_LEN, CHECKSUM_LEN, Frame, ScomTimeout, parse_frame, parse_header

@dataclass
class SerialSettings:
    # Xcom-232i: 38400 baud, 8 data bits, even parity, 1 stop bit (spec V1.5.16, 3.1).
    # The baud rate must equal the setting on the Xcom-232i. Other setups use 115200;
    # with a wrong rate you only get garbage, i.e. checksum errors or timeouts.
    # The response delay can reach 2 s (spec 3.7), so the timeout leaves some margin.
    port: str
    baudrate: int=38400
    timeout: float=3.0
    bytesize: int=8
    parity: str='E'
    stopbits: int=1

class ScomTransport:
    """Request/response over the Xcom-232i RS-232 port using Studer SCOM frames.

    It only sends frames the caller built; no write/configuration API is exposed.
    """
    def __init__(self, settings: SerialSettings, serial_obj=None):
        self.settings=settings
        if serial_obj is not None: self._serial=serial_obj
        else:
            try:
                import serial
            except ImportError as e: raise RuntimeError('pyserial is required for serial transport; install requirements.txt') from e
            self._serial=serial.Serial(**settings.__dict__)

    def _read_exact(self, size: int) -> bytes:
        data=self._serial.read(size)
        if len(data)!=size: raise ScomTimeout(f'expected {size} bytes, got {len(data)}')
        return data

    def request(self, raw: bytes) -> Frame:
        reset=getattr(self._serial,'reset_input_buffer',None)
        if reset: reset()  # drop stale bytes from an earlier timed-out exchange
        self._serial.write(raw)
        header=self._read_exact(HEADER_LEN)
        length=parse_header(header)[3]
        return parse_frame(header+self._read_exact(length+CHECKSUM_LEN))
