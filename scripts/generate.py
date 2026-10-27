#!/usr/bin/env python3
"""Generate the explicit 50-subchart POC; this file owns generated chart files."""
import argparse
import copy
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ['service-a', 'service-b'] + [f'service-{i:02d}' for i in range(3, 51)]
TENANT = {'name': 'default-tenant', 'domain': 'default-tenant.example.com', 'id': 'default', 'region': 'local', 'tier': 'standard', 'locale': 'en-IN', 'timezone': 'Asia/Kolkata'}
PLATFORM = {
    'platform': {'supportEmail': 'support@example.com', 'featureEnabled': False, 'displayName': 'Shared platform', 'sessionTimeoutSeconds': 1800, 'maintenance': {'enabled': False, 'message': 'Scheduled maintenance'}, 'branding': {'theme': 'light', 'primaryColor': '#3366ff'}},
    'routing': {'basePath': '/', 'tlsEnabled': True, 'requestTimeoutSeconds': 30, 'cors': {'enabled': True, 'allowedOrigins': ['https://app.example.com'], 'allowedMethods': ['GET', 'POST']}, 'rateLimit': {'enabled': True, 'requestsPerMinute': 1000}},
    'notifications': {'enabled': True, 'senderName': 'Platform', 'senderEmail': 'notifications@example.com', 'channels': ['email'], 'digest': {'enabled': True, 'hour': 9}, 'retry': {'maxAttempts': 3, 'backoffSeconds': 5}},
    'observability': {'logLevel': 'info', 'metrics': {'enabled': True, 'intervalSeconds': 30}, 'tracing': {'enabled': False, 'sampleRate': 0.1}, 'retentionDays': 14, 'labels': {'team': 'platform', 'environment': 'poc'}},
    'security': {'session': {'secureCookies': True, 'sameSite': 'Lax'}, 'passwordPolicy': {'minimumLength': 12, 'requireMfa': False}, 'audit': {'enabled': True, 'retentionDays': 90}, 'allowedCidrs': ['10.0.0.0/8']},
    'integrations': {'webhooks': {'enabled': False, 'timeoutSeconds': 10, 'events': ['tenant.created', 'order.created']}, 'exports': {'enabled': True, 'format': 'json', 'batchSize': 500}, 'externalApi': {'baseUrl': 'https://api.example.com', 'timeoutSeconds': 15}}
}
SERVICE_TEMPLATE = '''apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
  labels:
    poc.example.com/role: service
    poc.example.com/service: {{ .Chart.Name | quote }}
data:
  message: {{ .Values.message | quote }}
  environment: {{ .Values.settings.environment | quote }}
  logLevel: {{ .Values.settings.logLevel | quote }}
  tenantName: {{ .Values.global.tenant.name | quote }}
  tenantDomain: {{ .Values.global.tenant.domain | quote }}
  config.json: |
    {{- dict "tenant" .Values.global.tenant "message" .Values.message "settings" .Values.settings "runtime" .Values.runtime "resources" .Values.resources "features" .Values.features "retry" .Values.retry "tenantConfig" .Values.tenantConfig "integrations" .Values.integrations | toPrettyJson | nindent 4 }}
'''

def schema(value):
    if isinstance(value, dict):
        return {'type': 'object', 'properties': {k: schema(v) for k,v in value.items()}, 'required': list(value), 'additionalProperties': False}
    if isinstance(value, list):
        return {'type': 'array', 'items': schema(value[0]) if value else {}}
    if isinstance(value, bool): return {'type': 'boolean'}
    if isinstance(value, int): return {'type': 'integer', 'minimum': 0}
    if isinstance(value, float): return {'type': 'number', 'minimum': 0, 'maximum': 1}
    return {'type': 'string'}

def defaults(name, i):
    return {'global': {'tenant': copy.deepcopy(TENANT)}, 'message': f'{name} subchart default',
        'settings': {'environment': 'development', 'logLevel': 'info', 'port': 8000+i, 'timeoutSeconds': 15, 'allowedOrigins': ['https://default.example.com']},
        'runtime': {'replicas': 1, 'workers': 2, 'image': {'repository': f'example/{name}', 'tag': '1.0.0'}, 'health': {'path': '/healthz', 'intervalSeconds': 10}},
        'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}},
        'features': {'cacheEnabled': True, 'searchEnabled': False, 'betaEnabled': False},
        'retry': {'maxAttempts': 3, 'backoffSeconds': 2},
        'tenantConfig': {'displayName': 'Default workspace', 'quota': {'maxUsers': 100, 'maxProjects': 10}, 'tags': ['default']},
        'integrations': {'webhook': {'enabled': False, 'url': 'https://hooks.example.com/default'}, 'export': {'enabled': True, 'format': 'json'}}}

def render_files():
    files = {}
    def put(path, value):
        files[path] = yaml.safe_dump(value, sort_keys=False) if isinstance(value, dict) else value
    root = {'global': {'tenant': copy.deepcopy(TENANT)}, **copy.deepcopy(PLATFORM)}
    deps=[]
    for i,name in enumerate(SERVICES,1):
        base=defaults(name,i)
        put(f'charts/{name}/Chart.yaml', {'apiVersion':'v2','name':name,'description':f'{name} configuration-only subchart','type':'application','version':'0.2.0'})
        put(f'charts/{name}/values.yaml',base)
        service_schema=schema(base)
        # Helm injects parent globals, so future shared global keys may be added.
        service_schema['properties']['global']['additionalProperties']=True
        put(f'charts/{name}/values.schema.json', json.dumps(service_schema,indent=2)+'\n')
        put(f'charts/{name}/templates/configmap.yaml',SERVICE_TEMPLATE)
        root[name] = {'message': f'{name} configured by parent chart', 'settings': {'environment':'poc','logLevel':'debug' if i%2 else 'warn','timeoutSeconds':30+i}, 'runtime':{'replicas':2,'workers':4}, 'tenantConfig':{'quota':{'maxUsers':500,'maxProjects':50},'tags':['shared','poc']}}
        if name=='service-a': root[name]['message']='Service A overridden by the parent chart'
        if name=='service-b': root[name]['message']='Service B overridden by the parent chart'
        deps.append({'name':name,'version':'0.2.0','repository':f'file://charts/{name}'})
    put('Chart.yaml', {'apiVersion':'v2','name':'helm-values-poc','description':'50 services and six umbrella configurations with layered tenant overrides','type':'application','version':'0.4.0','dependencies':deps})
    put('values.yaml', '# GENERATED by scripts/generate.py; edit that source and regenerate.\n'+yaml.safe_dump(root,sort_keys=False))
    # Root schema allows partial service blocks, validated after merge by subcharts.
    root_schema=schema({'global':root['global'],**PLATFORM})
    root_schema['properties'].update({name:{'type':'object'} for name in SERVICES})
    root_schema['properties']['global']['properties']['tenant']['properties']['name']['minLength']=1
    root_schema['properties']['global']['properties']['tenant']['properties']['domain']['minLength']=1
    put('values.schema.json', json.dumps({'$schema':'http://json-schema.org/draft-07/schema#',**root_schema},indent=2)+'\n')
    for section in PLATFORM:
        template='''apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ printf "%s-SECTION" .Release.Name | trunc 63 | trimSuffix "-" }}
  labels:
    poc.example.com/role: umbrella
    poc.example.com/section: SECTION
data:
  tenantName: {{ .Values.global.tenant.name | quote }}
  tenantDomain: {{ .Values.global.tenant.domain | quote }}
'''.replace('SECTION',section)
        if section=='platform':
            template+='  supportEmail: {{ .Values.platform.supportEmail | quote }}\n  featureEnabled: {{ .Values.platform.featureEnabled | quote }}\n'
        template+='  config.json: |\n    {{- dict "tenant" .Values.global.tenant "settings" .Values.SECTION | toPrettyJson | nindent 4 }}\n'.replace('SECTION',section)
        put('templates/'+('tenant-config' if section=='platform' else section)+'.yaml', template)
    return files

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true'); args=parser.parse_args()
    mismatches=[]
    for relative,content in render_files().items():
        path=ROOT/relative
        if args.check:
            if not path.exists() or path.read_text()!=content: mismatches.append(relative)
        else:
            path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    if mismatches: raise SystemExit('Regenerate files: '+', '.join(mismatches))
    print(('Checked' if args.check else 'Generated')+' 50 subcharts and six umbrella templates.')
