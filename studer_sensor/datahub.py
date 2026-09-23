import json, urllib.request, urllib.error
from .telemetry import utc_now
class DataHubError(Exception): pass
class DataHubClient:
    def __init__(self, base_url, api_key, timeout=10): self.url=base_url.rstrip('/')+'/api/ingest/studer-xcom'; self.api_key=api_key; self.timeout=timeout
    def ingest(self,payload):
        payload = dict(payload)
        payload.setdefault("timestamp", utc_now())
        req=urllib.request.Request(self.url,data=json.dumps(payload).encode(),headers={'x-api-key':self.api_key,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r: return r.status
        except urllib.error.HTTPError as e:
            raise DataHubError(f"DataHub returned HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise DataHubError(str(e)) from e
