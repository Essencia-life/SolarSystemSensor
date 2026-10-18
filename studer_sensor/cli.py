import argparse
import logging
import signal
from .config import ServiceConfig
from .discovery import discover_scom
from .service import CollectorService
from .spool import Spool
from .datahub import DataHubClient
from .telemetry import Collector
from .transport import SerialSettings, ScomTransport
from .scom import ScomReader, parse_queries

def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Studer telemetry service")
    parser.add_argument("--once", action="store_true", help="collect one cycle and exit")
    args = parser.parse_args(argv)
    config = ServiceConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    settings = SerialSettings(config.serial_port, config.serial_baudrate, config.serial_timeout,
                              parity=config.serial_parity)
    reader = ScomReader(ScomTransport(settings), parse_queries(config.scom_infos),
                        config.scom_src_addr)
    collector = Collector(reader, reader.definitions())
    service = CollectorService(collector, DataHubClient(config.datahub_url,
        config.datahub_api_key, config.datahub_timeout), Spool(config.spool_path),
        config.device_id, config.poll_interval)
    signal.signal(signal.SIGTERM, lambda *_: service.stop())
    signal.signal(signal.SIGINT, lambda *_: service.stop())
    service.run(max_cycles=1 if args.once else None)
    return 0

if __name__ == "__main__":
    main()
