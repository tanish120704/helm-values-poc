# 50-service Helm values POC

This repository is an umbrella Helm chart with **50 application subcharts** and
**six standalone umbrella templates**. Each tenant renders **56 ConfigMaps**.
These are configuration snapshots, not running services or a workload capacity
benchmark. Domains and external URLs are illustrative; no DNS or ingress is created.

## What is included

- Services: `service-a`, `service-b`, and `service-03` through `service-50`.
- Every service has its own `Chart.yaml`, defaults, JSON schema, and template.
- Service settings cover environment, logs, ports, timeouts, origins, replicas,
  workers, image repository/tag, health checks, CPU/memory, feature flags,
  retries, quotas, tags, webhooks, and exports.
- Root `values.yaml` overrides selected subchart defaults for all 50 services.
- Shared `global.tenant` includes name, domain, ID, region, tier, locale, timezone.
- Root templates: platform, routing, notifications, observability, security,
  integrations. Each has multiple nested defaults in root `values.yaml`.
- Each ConfigMap exposes effective configuration as `data["config.json"]` plus
  tenant identity fields. Existing service flat fields remain available.
- No credentials or real secrets belong in these values or ConfigMaps.

```text
Chart.yaml                     # 50 local dependencies; umbrella version 0.4.0
values.yaml                    # Umbrella defaults and service parent overrides
values.schema.json             # Umbrella configuration validation
charts/
  service-a/                   # Plus service-b and service-03 ... service-50
    Chart.yaml
    values.yaml
    values.schema.json
    templates/configmap.yaml
templates/
  tenant-config.yaml           # Platform
  routing.yaml
  notifications.yaml
  observability.yaml
  security.yaml
  integrations.yaml
scripts/
  generate.py                  # Reproducible source for generated chart files
  verify.py                    # Local render and deployed configuration checks
  requirements.txt
```

## Layering and GitOps

For services: subchart defaults → parent service block → tenant service block.
For umbrella templates: root defaults → tenant root block.
Parent `global.tenant` is shared with every subchart and root template.
Nested maps merge, supplied lists replace lists, and false/zero remain overrides.
Values are configuration data; text containing Helm expressions is not evaluated.

The private [GitOps repository](https://github.com/tanish120704/argocd-gitops-poc)
contains tenant values and the ApplicationSet. Each tenant Application combines
this chart with `tenants/<tenant-id>/values.yaml` from that repository. Commit
and push changes; no manual tenant Application or Kubernetes apply is needed.

- **Tenant One**: baseline identity; inherits all service and umbrella defaults.
- **Tenant B**: customizes 10 services (`a`, `b`, `03`, `10`, `15`, `20`, `25`,
  `30`, `40`, `50`) and all six umbrella sections; 40 services inherit defaults.
- Service A demonstrates disabled cache, zero retries, image/replica changes,
  nested resource overrides and quota overrides.
- Service B demonstrates an empty origins list and an overridden webhook URL.
- Umbrella integration events also demonstrate an explicit empty list.

## Validate and inspect

Requires Helm 3+, Python 3.9+, and the pinned Python dependency:

```sh
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/generate.py --check
helm lint . --with-subcharts
helm template tenant-b . -f ../argocd-gitops-poc/tenants/tenant-b/values.yaml
.venv/bin/python scripts/verify.py --release tenant-b \
  --tenant-values ../argocd-gitops-poc/tenants/tenant-b/values.yaml
```

The verifier independently merges the actual checked-in defaults and tenant
values, then checks every effective field in all 56 ConfigMaps. It covers
nested inheritance, list replacement, booleans, numeric zero, shared identity,
and resource counts. JSON schemas reject misspelled fields and wrong types.

Verify the deployed configuration with the same checks:

```sh
kubectl --context colima -n tenant-tenant-b get configmaps -o json > /tmp/tenant-b-configmaps.json
.venv/bin/python scripts/verify.py --release tenant-b \
  --tenant-values ../argocd-gitops-poc/tenants/tenant-b/values.yaml \
  --live-list /tmp/tenant-b-configmaps.json
```

Repeat for `tenant-one` / `tenant-tenant-one` to check inherited defaults.

## Maintain this generated fixture

`scripts/generate.py` owns the generated chart metadata, values, schemas, and
templates. Change that source and run `python scripts/generate.py`; review the
resulting files and commit both source and output. Tenant overrides are edited
only in the GitOps repo. Verification does not import the generator: it reads
the rendered resources and actual chart values independently.

## Direct Helm group entry points

`groups/` adds four small umbrella charts without moving or changing any existing
subcharts, root templates, or root values. Group dependencies reference the
existing service charts through local `file://../../charts/<service>` paths.
Standard `Chart.lock` files pin dependency metadata. Argo CD builds missing local
dependencies automatically; for local use, run `helm dependency build` first.

| Group | Services | Root templates |
| --- | --- | --- |
| foundation | service-a, service-b, service-03 through service-12 | All six |
| core-platform | service-13 through service-25 | None |
| product-services | service-26 through service-40 | None |
| to-revisit | service-41 through service-50 | None |

Foundation uses repository-local symbolic links to the six existing root
templates. Their original files remain the single source of template content.
The original root chart remains usable for a complete 56-resource render.

```sh
helm dependency build groups/foundation
helm template tenant-b groups/foundation -f values.yaml \
  -f ../argocd-gitops-poc/tenants/tenant-b/values.yaml
```

The GitOps repository's parent Helm chart renders four child Applications. Each
child renders its own group directly in Argo CD, loading root values followed by
tenant values. There is no pre-rendered-manifest pipeline. Services retain the
same values keys and Kubernetes resource names. A service change can change its
group's rendered output; shared values used by several groups may affect all of
them. Shared repositories can cause refreshes without manifest changes or syncs.

Both repos track `main` for this POC; production version promotion is a separate
concern. Group membership is defined by these four dependency lists, not a
second service catalog or a custom generation tool.
