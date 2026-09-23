from dataclasses import dataclass
from datetime import datetime, timezone
@dataclass(frozen=True)
class MetricDefinition:
    name: str; unit: str|None=None; scale: float=1.0
METRICS={}
def normalize(values: dict, definitions=METRICS) -> dict:
    out={}
    for name, definition in definitions.items():
        if name in values and values[name] is not None:
            try: out[name]={'value':float(values[name])*definition.scale,'unit':definition.unit}
            except (TypeError,ValueError): pass
    return out
class Collector:
    def __init__(self, reader, definitions=METRICS): self.reader=reader; self.definitions=definitions
    def collect(self): return normalize(self.reader(),self.definitions)
def utc_now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
