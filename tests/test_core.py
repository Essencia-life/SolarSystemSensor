from studer_sensor.telemetry import *
from studer_sensor.spool import Spool
from studer_sensor.discovery import Device, discover_devices
from studer_sensor.discovery import SCOMDevice, discover_scom
from studer_sensor.datahub import DataHubClient
from studer_sensor.config import ServiceConfig
from studer_sensor.service import CollectorService
import json
import urllib.error

def test_missing_metrics():
 assert normalize({'x':'2'},{'x':MetricDefinition('x','V',2),'y':MetricDefinition('y')})['x']['value']==4

def test_spool(tmp_path):
 s=Spool(str(tmp_path/'x.db')); s.enqueue({'a':1},'2020Z'); row=s.due()[0]; assert row['created']=='2020Z'; assert row['payload']=={'a':1}; s.acknowledge(row['id']); assert not s.due()

def test_discovery_provider():
 assert discover_devices(lambda: [Device('/dev/test', 'mock')])[0].port == '/dev/test'

def test_datahub_request(monkeypatch):
 seen={}
 class Response:
  status=202
  def __enter__(self): return self
  def __exit__(self,*args): pass
 def opener(req, timeout):
  seen.update(url=req.full_url, key=req.headers['X-api-key'], body=json.loads(req.data))
  return Response()
 monkeypatch.setattr('urllib.request.urlopen', opener)
 assert DataHubClient('https://example.test', 'secret').ingest({'metrics': {}}) == 202
 assert seen['url'].endswith('/api/ingest/studer-xcom')
 assert seen['key'] == 'secret'
 assert seen['body']['timestamp'].endswith('Z')

def test_config_from_env():
 cfg = ServiceConfig.from_env({'SERIAL_PORT':'p','DATAHUB_URL':'u','DATAHUB_API_KEY':'k','DEVICE_ID':'d',
                               'POLL_INTERVAL':'2','LOG_LEVEL':'DEBUG'})
 assert cfg.serial_port == 'p' and cfg.poll_interval == 2 and cfg.log_level == 'DEBUG'

def test_scom_discovery_provider():
 found = discover_scom(b'read-only', lambda query: [{'id':'x','model':'mock'}])
 assert found == [SCOMDevice('x', {'id':'x','model':'mock'})]

def test_service_collects_and_drains():
 class Sp:
  def __init__(self): self.rows=[]; self.acked=[]
  def enqueue(self,payload,created): self.rows.append({'id':1,'payload':payload,'created':created,'attempts':0})
  def due(self): return self.rows
  def acknowledge(self,i): self.acked.append(i); self.rows.clear()
  def close(self): pass
 class Col:
  def collect(self): return {'v': {'value': 1}}
 class Client:
  def __init__(self): self.sent=[]
  def ingest(self,p): self.sent.append(p)
 sp, client = Sp(), Client()
 CollectorService(Col(), client, sp, 'd').run(max_cycles=1)
 assert client.sent[0]['deviceId'] == 'd'
 assert client.sent[0]['values'] == [{'metric': 'v', 'value': 1, 'unit': None}]
 assert sp.acked == [1]

def test_spool_retry_delay_is_capped(tmp_path):
 import time
 s=Spool(str(tmp_path/'x.db'), base_delay=1, max_delay=300); s.enqueue({'a':1},'2020Z'); rid=s.due()[0]['id']
 before=time.time(); s.retry(rid, 0); assert 0.5 < s.db.execute('select next_try from queue').fetchone()[0]-before < 2   # 1 s
 before=time.time(); s.retry(rid, 5); assert 30 < s.db.execute('select next_try from queue').fetchone()[0]-before < 34   # 32 s
 before=time.time(); s.retry(rid, 40); assert 299 < s.db.execute('select next_try from queue').fetchone()[0]-before < 302  # capped, no overflow
 before=time.time(); s.retry(rid, 100000); assert 299 < s.db.execute('select next_try from queue').fetchone()[0]-before < 302
