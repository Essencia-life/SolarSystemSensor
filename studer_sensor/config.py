"""Environment-based service configuration."""
from __future__ import annotations

from dataclasses import dataclass
import os

def _required(name, env=None):
    value = (os.environ if env is None else env).get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value

@dataclass(frozen=True)
class ServiceConfig:
    serial_port: str
    datahub_url: str
    datahub_api_key: str
    device_id: str
    poll_interval: float = 30.0
    spool_path: str = "spool.sqlite3"
    log_level: str = "INFO"
    # Baud rate = serial transmission speed in bits per second. Sender and receiver must use
    # the same value, otherwise every frame arrives garbled (checksum errors / timeouts).
    # 38400 is the value in the protocol spec V1.5.16; the Xcom-232i itself is configurable
    # and some setups use 115200. Set SERIAL_BAUDRATE to match the device, see docs/INSTALL.md.
    serial_baudrate: int = 38400
    serial_timeout: float = 3.0
    serial_parity: str = "E"
    datahub_timeout: float = 10.0
    scom_src_addr: int = 1
    scom_infos: str | None = None

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        get = lambda key, default=None: env.get(key, default)
        return cls(serial_port=env.get("SERIAL_PORT") or _required("SERIAL_PORT", env),
                   datahub_url=env.get("DATAHUB_URL") or _required("DATAHUB_URL", env),
                   datahub_api_key=env.get("DATAHUB_API_KEY") or _required("DATAHUB_API_KEY", env),
                   device_id=env.get("DEVICE_ID") or _required("DEVICE_ID", env),
                   poll_interval=float(get("POLL_INTERVAL", 30)),
                   spool_path=get("SPOOL_PATH", "spool.sqlite3"),
                   log_level=get("LOG_LEVEL", "INFO"),
                   serial_baudrate=int(get("SERIAL_BAUDRATE", 38400)),
                   serial_timeout=float(get("SERIAL_TIMEOUT", 3)),
                   serial_parity=get("SERIAL_PARITY", "E").upper(),
                   datahub_timeout=float(get("DATAHUB_TIMEOUT", 10)),
                   scom_src_addr=int(get("SCOM_SRC_ADDR", 1)),
                   scom_infos=get("SCOM_INFOS") or None)
