import logging
from pathlib import Path

import jubilant
import pytest
import tenacity
import yaml
from charmed_kubeflow_chisme.kubernetes import (
    KubernetesResourceHandler,
    create_charm_default_labels,
)
from lightkube.generic_resource import create_namespaced_resource
from lightkube.resources.core_v1 import Namespace, Secret

from charm import SECRET_NAME

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
CHARM_NAME = METADATA["name"]

OFFLINE_STORE_APP_NAME = "offline-store"
ONLINE_STORE_APP_NAME = "online-store"
REGISTRY_APP_NAME = "registry"

ADMISSION_WEBHOOK_CHARM_NAME = "admission-webhook"
RESOURCE_DISPATCHER_CHARM_NAME = "resource-dispatcher"
METACONTROLLER_CHARM_NAME = "metacontroller-operator"

NAMESPACE_FILE = "./tests/integration/namespace.yaml"
NAMESPACE_NAME = yaml.safe_load(Path(NAMESPACE_FILE).read_text())["metadata"]["name"]

PODDEFAULT_NAME = f"{CHARM_NAME}-access-feast"

PodDefault = create_namespaced_resource("kubeflow.org", "v1alpha1", "PodDefault", "poddefaults")


@pytest.fixture(scope="module")
def k8s_resource_handler(juju: jubilant.Juju) -> KubernetesResourceHandler:
    k8s_resource_handler = KubernetesResourceHandler(
        field_manager=CHARM_NAME,
        template_files=[NAMESPACE_FILE],
        labels=create_charm_default_labels(
            application_name=CHARM_NAME,
            model_name=juju.model,
            scope="namespace",
        ),
        resource_types={Namespace},
        context={},
    )
    return k8s_resource_handler


@pytest.fixture(scope="module")
def namespace(k8s_resource_handler: KubernetesResourceHandler):
    k8s_resource_handler.apply()
    yield NAMESPACE_NAME

    k8s_resource_handler.delete()


def test_deploy_charm(juju: jubilant.Juju, request):
    """Test deploy the charm and its dependencies go to active."""
    # Deploy Feast Integrator
    juju.deploy(charm=request.config.getoption("--charm-path"))

    # Check the charm to be blocked due to missing relations
    juju.wait(lambda status: status.apps[CHARM_NAME].is_blocked)

    # Deploy 3 Postgresql charms as offline store, online store, registry
    for db_type in [OFFLINE_STORE_APP_NAME, ONLINE_STORE_APP_NAME, REGISTRY_APP_NAME]:
        juju.deploy(
            charm="postgresql-k8s",
            app=db_type,
            channel="14/stable",
            trust=True,
            config={"profile": "testing"},
        )

        # Integrate with each DB charm
        juju.integrate(f"{CHARM_NAME}:{db_type}", db_type)

    # Deploy metacontroller due to resource-dispatcher depending on the DecoratorController CRD
    juju.deploy(
        charm=METACONTROLLER_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    # Deploy resource-dispatcher
    juju.deploy(charm=RESOURCE_DISPATCHER_CHARM_NAME, channel="latest/edge", trust=True)

    juju.integrate(f"{CHARM_NAME}:secrets", f"{RESOURCE_DISPATCHER_CHARM_NAME}:secrets")
    juju.integrate(f"{CHARM_NAME}:pod-defaults", f"{RESOURCE_DISPATCHER_CHARM_NAME}:pod-defaults")

    # Deploy admission webhook to get the poddefaults CRD
    juju.deploy(
        charm=ADMISSION_WEBHOOK_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    juju.wait(jubilant.all_active)


RETRY_FOR_THREE_MINUTES = tenacity.Retrying(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=15),
    stop=tenacity.stop_after_delay(600),
    reraise=True,
)


def test_new_user_namespace_has_manifests(
    juju: jubilant.Juju, k8s_resource_handler: KubernetesResourceHandler, namespace: str
):
    """Test that the user namespace has the Secret and PodDefault with the expected attributes."""
    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            secret = k8s_resource_handler.lightkube_client.get(
                Secret, SECRET_NAME, namespace=namespace
            )
            pod_default = k8s_resource_handler.lightkube_client.get(
                PodDefault, PODDEFAULT_NAME, namespace=namespace
            )

    # Assert Secret has the expected data field
    assert secret.data.get("feature_store.yaml")

    # Assert PodDefault attributes
    poddefault_secret_name = (
        pod_default.get("spec", {}).get("volumes", [])[0].get("secret", {}).get("secretName")
    )
    assert poddefault_secret_name == SECRET_NAME

    selector_label = pod_default.get("spec", {}).get("selector", {}).get("matchLabels")
    assert selector_label == {"access-feast": "true"}
