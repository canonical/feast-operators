"""Charms dependencies for Feast UI integration tests."""

from charmed_kubeflow_chisme.testing import CharmSpec

OFFLINE_STORE = CharmSpec(
    charm="postgresql-k8s", channel="14/stable", trust=True, config={"profile": "testing"}
)
ONLINE_STORE = CharmSpec(
    charm="postgresql-k8s", channel="14/stable", trust=True, config={"profile": "testing"}
)
REGISTRY = CharmSpec(
    charm="postgresql-k8s", channel="14/stable", trust=True, config={"profile": "testing"}
)

FEAST_INTEGRATOR = CharmSpec(charm="feast-integrator", channel="latest/edge", trust=True)
METACONTROLLER = CharmSpec(charm="metacontroller-operator", channel="latest/edge", trust=True)
RESOURCE_DISPATCHER = CharmSpec(charm="resource-dispatcher", channel="latest/edge", trust=True)
ADMISSION_WEBHOOK = CharmSpec(charm="admission-webhook", channel="latest/edge", trust=True)

ISTIO_GATEWAY = CharmSpec(
    charm="istio-gateway", channel="latest/edge", trust=True, config={"kind": "ingress"}
)
ISTIO_PILOT = CharmSpec(
    charm="istio-pilot",
    channel="latest/edge",
    trust=True,
    config={"default-gateway": "istio-gateway"},
)
