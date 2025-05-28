# Feast UI Operator

The Feast UI Charm provides a Kubernetes-native deployment of the [Feast UI](https://docs.feast.dev/) — a web interface for interacting with Feast feature stores — powered by Juju and Charmed Operators.

## Features

- Deploys the Feast UI web frontend in a containerized environment.
- Integrates with Istio for ingress via Juju's `ingress` relation.
- Connects with the Feast Integrator charm to retrieve project registry information.

## Deployment

To deploy this charm:

```bash
juju deploy feast-ui --trust --resource oci-image=<feast-ui-image>
```

Make sure you have a valid OCI image published or accessible for `feast-ui`.

## Relations

This charm supports the following relations:

- `ingress` (required): for exposing the UI via Istio ingress
- `feast-configuration` (required): receives registry info and config from the Feast Integrator
- `dashboard-links` (required): for integrating UI via kubeflow-dashboard

To relate with Istio ingress:

```bash
juju deploy istio-gateway --channel=latest/edge --trust --config kind=ingress
juju deploy istio-pilot --channel=latest/edge --trust --config default-gateway=istio-gateway
juju integrate istio-pilot:ingress feast-ui:ingress
```

To relate with Feast Integrator:

```bash
juju integrate feast-integrator:feast-configuration feast-ui:feast-configuration
```

## Development & Testing

Run integration tests using the `jubilant` test harness:

```bash
tox -e unit
tox -e integration
```

These tests cover:
- Charm deployment
- Configuration propagation
- Integration with Istio and Feast Integrator