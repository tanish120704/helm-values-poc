#!/usr/bin/env python3
"""Exercise Service B processing defaults, overrides, inheritance, and schema failures."""
import argparse, copy, json, subprocess, tempfile
from pathlib import Path
import yaml
p=argparse.ArgumentParser(); p.add_argument('--helm',default='helm'); p.add_argument('--tenant-values',required=True); args=p.parse_args()
root=Path(__file__).resolve().parents[1]; tenant=yaml.safe_load(Path(args.tenant_values).read_text())
def render(overrides,success=True):
 values=copy.deepcopy(tenant)
 if overrides is None: values['service-b'].pop('processing',None)
 else: values['service-b']['processing']=overrides
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'values.yaml'; path.write_text(yaml.safe_dump(values))
  r=subprocess.run([args.helm,'template','tenant-b',str(root/'groups/foundation'),'-f',str(root/'values.yaml'),'-f',str(path)],capture_output=True,text=True)
 if not success:
  assert r.returncode and 'schema' in r.stderr.lower(),r.stderr
  return
 assert r.returncode==0,r.stderr
 docs={d['metadata']['name']:d for d in yaml.safe_load_all(r.stdout) if d}
 assert len(docs)==18
 service=docs['tenant-b-service-b']; data=service['data']; processing=json.loads(data['processing.json'])
 assert processing==json.loads(data['config.json'])['processing']
 assert all(isinstance(value,str) for doc in docs.values() for value in doc['data'].values())
 return processing,docs
expected={'enabled':True,'maxInFlight':32,'allowedQueues':['default'],'backoff':{'initialSeconds':1,'maxSeconds':60}}
assert render(None)[0]==expected
print('PASS omitted overrides: subchart defaults and root defaults merge correctly')
edge={'enabled':False,'maxInFlight':0,'allowedQueues':[],'backoff':{'initialSeconds':0}}
actual,base=render(edge)
assert actual=={'enabled':False,'maxInFlight':0,'allowedQueues':[],'backoff':{'initialSeconds':0,'maxSeconds':60}}
print('PASS false, zero, empty list, and partial nested map: values retained; maxSeconds inherited from root')
assert render({'allowedQueues':['priority']})[0]['allowedQueues']==['priority']
print('PASS non-empty list replaces the default list')
assert render({'maxInFlight':7})[0]=={**expected,'maxInFlight':7}
print('PASS omitted siblings retain their inherited values')
assert render(None)[0]==expected
print('PASS removing the processing override restores inherited defaults')
for label,value in [
 ('boolean string',{'enabled':'false'}),('negative integer',{'maxInFlight':-1}),
 ('numeric string',{'maxInFlight':'0'}),('list string',{'allowedQueues':'default'}),
 ('invalid list member',{'allowedQueues':[False]}),('unknown setting',{'maxInflight':1}),
 ('null block',None),('null required nested field',{'backoff':{'initialSeconds':None}})]:
 if label=='null block':
  # Explicit null differs from omitting the override; use a separate render invocation.
  values=copy.deepcopy(tenant); values['service-b']['processing']=None
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'values.yaml'; path.write_text(yaml.safe_dump(values))
   r=subprocess.run([args.helm,'template','tenant-b',str(root/'groups/foundation'),'-f',str(root/'values.yaml'),'-f',str(path)],capture_output=True,text=True)
  assert r.returncode and 'schema' in r.stderr.lower(),r.stderr
 else: render(value,success=False)
 print('PASS schema rejects '+label)
# Confirm a valid override only changes the Service B resource within Foundation.
_,modified=render({'maxInFlight':7})
assert [key for key in modified if modified[key]!=base[key]]==['tenant-b-service-b']
print('PASS processing overrides affect only Service B in Foundation')
