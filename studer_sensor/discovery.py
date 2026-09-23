"""Separate host serial enumeration from read-only SCOM discovery."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Device:
    port: str
    description: str = ""
    serial_number: str | None = None

@dataclass(frozen=True)
class SCOMDevice:
    identifier: str
    attributes: dict

def list_serial_ports(provider=None) -> list[Device]:
    if provider is not None:
        return list(provider())
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [Device(p.device, p.description or "", p.serial_number)
            for p in list_ports.comports()]

def discover_scom(query, provider) -> list[SCOMDevice]:
    """Run an injected, read-only SCOM query and normalize its result."""
    result = provider(query)
    return [item if isinstance(item, SCOMDevice)
            else SCOMDevice(str(item.get("identifier", item.get("id", ""))),
                            dict(item))
            for item in result]

# Backward-compatible name for host port listing.
discover_devices = list_serial_ports
