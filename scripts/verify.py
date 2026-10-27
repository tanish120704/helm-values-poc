#!/usr/bin/env python3
"""Check all effective ConfigMap data against independent layered value merges."""
import argparse
import copy
import json
import subprocess
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
def load(path): return yaml.safe_load(Path(path).read_text())
def merge(base, override):
    result=copy.deepcopy(base)
    for key,value in override.items():
        if isinstance(value,dict) and isinstance(result.get(key),dict): result[key]=merge(result[key],value)
        else: result[key]=copy.deepcopy(value)
    return result

def verify(tenant_file, release, documents):
    parent=load(ROOT/'values.yaml'); tenant=load(tenant_file)
    effective=merge(parent,tenant)
    dependencies=load(ROOT/'Chart.yaml')['dependencies']
    names={d['name'] for d in dependencies}
    sections=set(parent)-names-{'global'}
    assert len(names)==50 and len(sections)==6
    expected={}
    for name in names:
        values=merge(merge(load(ROOT/'charts'/name/'values.yaml'),parent.get(name,{})),tenant.get(name,{}))
        values['global']=merge(values.get('global',{}),effective['global'])
        expected[release+'-'+name]={'tenant':values['global']['tenant'],**{k:v for k,v in values.items() if k!='global'}}
    for section in sections:
        expected[release+'-'+section]={'tenant':effective['global']['tenant'],'settings':effective[section]}
    actual={doc['metadata']['name']:doc for doc in documents if doc and doc.get('kind')=='ConfigMap' and 'config.json' in doc.get('data',{})}
    assert set(actual)==set(expected), {'missing':sorted(set(expected)-set(actual)), 'extra':sorted(set(actual)-set(expected))}
    for name,value in expected.items():
        doc=actual[name]; data=doc['data']; got=json.loads(data['config.json'])
        assert got==value, f'{name}: effective configuration differs\nexpected={value}\nactual={got}'
        assert all(isinstance(v,str) for v in data.values()), f'{name}: ConfigMap data must be strings'
        assert data['tenantName']==effective['global']['tenant']['name']
        assert data['tenantDomain']==effective['global']['tenant']['domain']
    assert sum(d['metadata']['labels']['poc.example.com/role']=='service' for d in actual.values())==50
    assert sum(d['metadata']['labels']['poc.example.com/role']=='umbrella' for d in actual.values())==6
    print(f'{release}: verified all 56 ConfigMaps, every nested value, inherited defaults, tenant identity, and service/umbrella overrides.')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--tenant-values',required=True); p.add_argument('--release',required=True); p.add_argument('--helm',default='helm'); p.add_argument('--live-list',help='kubectl get configmaps -o json output'); args=p.parse_args()
    if args.live_list: documents=json.loads(Path(args.live_list).read_text())['items']
    else:
        result=subprocess.run([args.helm,'template',args.release,str(ROOT),'-f',args.tenant_values],check=True,capture_output=True,text=True)
        documents=list(yaml.safe_load_all(result.stdout))
    verify(args.tenant_values,args.release,documents)
