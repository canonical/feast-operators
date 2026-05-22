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

FEAST_INTEGRATOR = CharmSpec(charm="feast-integrator", channel="0.49/edge", trust=True)
METACONTROLLER = CharmSpec(charm="metacontroller-operator", channel="4.11/edge", trust=True)
RESOURCE_DISPATCHER = CharmSpec(charm="resource-dispatcher", channel="2.0/edge", trust=True)
ADMISSION_WEBHOOK = CharmSpec(charm="admission-webhook", channel="1.10/edge", trust=True)

ISTIO_GATEWAY = CharmSpec(
    charm="istio-gateway", channel="1.28/edge", trust=True, config={"kind": "ingress"}
)
ISTIO_PILOT = CharmSpec(
    charm="istio-pilot",
    channel="1.28/edge",
    trust=True,
    config={"default-gateway": "istio-gateway"},
)
