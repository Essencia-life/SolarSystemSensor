"""Polling service orchestration, with no device writes beyond request framing."""
import logging
import threading
import time
from .datahub import DataHubError
from .telemetry import utc_now

class CollectorService:
    def __init__(self, collector, client, spool, device_id, interval=30.0,
                 sleeper=time.sleep, logger=None):
        self.collector, self.client, self.spool = collector, client, spool
        self.device_id, self.interval = device_id, interval
        self.sleeper, self.log = sleeper, logger or logging.getLogger(__name__)
        self._stop = threading.Event()

    def stop(self): self._stop.set()

    def run(self, max_cycles=None):
        cycles = 0
        try:
            while not self._stop.is_set() and (max_cycles is None or cycles < max_cycles):
                try:
                    metrics = self.collector.collect()
                    values = [
                        {"metric": name, "value": item["value"], "unit": item.get("unit")}
                        for name, item in metrics.items()
                    ]
                    self.spool.enqueue({"deviceId": self.device_id, "timestamp": utc_now(),
                                        "values": values}, utc_now())
                except Exception:
                    self.log.exception("telemetry collection failed")
                for record in self.spool.due():
                    try:
                        self.client.ingest(record["payload"])
                        self.spool.acknowledge(record["id"])
                    except DataHubError:
                        self.spool.retry(record["id"], record["attempts"])
                        self.log.warning("DataHub delivery failed; queued for retry")
                cycles += 1
                if max_cycles is None: self._stop.wait(self.interval)
        finally:
            self.spool.close()

def build_service(config, collector, client_factory, spool_factory):
    from .datahub import DataHubClient
    client = client_factory(config.datahub_url, config.datahub_api_key, config.datahub_timeout)
    return CollectorService(collector, client, spool_factory(config.spool_path),
                            config.device_id, config.poll_interval)
