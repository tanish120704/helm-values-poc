# Helm subchart values POC

This repository is a parent Helm chart with two local subcharts. Each subchart
defines its own defaults. The parent's `values.yaml` overrides those defaults
under keys matching the dependency names in `Chart.yaml`.

```text
.
├── Chart.yaml
├── values.yaml
└── charts/
    ├── service-a/
    │   ├── Chart.yaml
    │   ├── values.yaml
    │   └── templates/configmap.yaml
    └── service-b/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/configmap.yaml
```

Helm uses the case-sensitive filename `Chart.yaml` and loads subcharts from
`charts/`. Both dependencies are included as source, so rendering requires no
external chart repository or Kubernetes cluster.

## Render the parent chart

Run from this repository with Helm 3 or later:

```sh
helm lint . --with-subcharts
helm template poc .
```

The parent values file is loaded automatically; no `-f` flag is needed.
The rendered ConfigMaps contain:

| ConfigMap | message | environment | logLevel |
| --- | --- | --- | --- |
| poc-service-a | Service A overridden by the parent chart | poc | debug |
| poc-service-b | Service B overridden by the parent chart | poc | warn |

## Compare standalone subchart defaults

```sh
helm template poc ./charts/service-a
helm template poc ./charts/service-b
```

Standalone rendering uses each subchart's own `values.yaml`: the environment
is `development`, and the messages are `Service A default message` and
`Service B default message`. The log levels are `info` and `error`, respectively.

Within a subchart, templates read `.Values.message` and `.Values.settings.*`.
Helm passes the parent's `service-a` or `service-b` section into that subchart's
values scope; the subchart does not need to reference the parent chart directly.

To try another parent-level override:

```sh
helm template poc . --set service-a.settings.logLevel=trace
```

Reference: [Helm chart structure and dependencies](https://helm.sh/docs/topics/charts/).

## Tenant identity and GitOps

The parent `values.yaml` defines shared service defaults and a default
`global.tenant` identity. Both subcharts read `.Values.global.tenant.name` and
`.Values.global.tenant.domain`. Helm shares the parent's `global` values with
both subcharts automatically. Subcharts also have defaults for standalone use.

Tenant files live in the separate
[argocd-gitops-poc repository](https://github.com/tanish120704/argocd-gitops-poc)
under `tenants/<tenant-id>/values.yaml`, for example:

```yaml
global:
  tenant:
    name: tenant-one
    domain: tenant-one.example.com
```

That repository's ApplicationSet discovers tenant files and generates an
Application per tenant, using this chart plus the tenant values file. The
parent defaults load automatically; the tenant file overrides only its supplied
keys. Tenant values may also override service-specific settings if needed.

```sh
helm template tenant-one . -f ../argocd-gitops-poc/tenants/tenant-one/values.yaml
```

This POC renders two ConfigMaps, not running service containers. Tenant identity
is visible in both ConfigMaps; tenant domains do not provision DNS or ingress.
