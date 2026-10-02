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
    serial_baudrate: int = 9600
    serial_timeout: float = 1.0
    datahub_timeout: float = 10.0
    query_hex: str | None = None

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
                   serial_baudrate=int(get("SERIAL_BAUDRATE", 9600)),
                   serial_timeout=float(get("SERIAL_TIMEOUT", 1)),
                   datahub_timeout=float(get("DATAHUB_TIMEOUT", 10)),
                   query_hex=get("SCOM_QUERY_HEX"))
