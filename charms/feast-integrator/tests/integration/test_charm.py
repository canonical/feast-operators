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

TESTER_CHARM_NAME = "configuration-requirer-tester"


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
    for db_charm in [OFFLINE_STORE_APP_NAME, ONLINE_STORE_APP_NAME, REGISTRY_APP_NAME]:
        juju.deploy(
            charm="postgresql-k8s",
            app=db_charm,
            channel="14/stable",
            trust=True,
            config={"profile": "testing"},
        )

    # Wait for Postgresql charms to be active
    juju.wait(
        lambda status: jubilant.all_active(
            status, [OFFLINE_STORE_APP_NAME, ONLINE_STORE_APP_NAME, REGISTRY_APP_NAME]
        ),
    )

    # Integrate with each DB charm
    for db_charm in [OFFLINE_STORE_APP_NAME, ONLINE_STORE_APP_NAME, REGISTRY_APP_NAME]:
        juju.integrate(f"{CHARM_NAME}:{db_charm}", db_charm)

    # Deploy metacontroller due to resource-dispatcher depending on the DecoratorController CRD
    juju.deploy(
        charm=METACONTROLLER_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    # Deploy resource-dispatcher
    juju.deploy(charm=RESOURCE_DISPATCHER_CHARM_NAME, channel="latest/edge", trust=True)

    # Deploy admission webhook to get the poddefaults CRD
    juju.deploy(
        charm=ADMISSION_WEBHOOK_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    # Wait for dependency charms to be active
    juju.wait(
        lambda status: jubilant.all_active(
            status,
            [
                METACONTROLLER_CHARM_NAME,
                RESOURCE_DISPATCHER_CHARM_NAME,
                ADMISSION_WEBHOOK_CHARM_NAME,
            ],
        ),
    )

    # Relate to resource-dispatcher
    juju.integrate(f"{CHARM_NAME}:secrets", f"{RESOURCE_DISPATCHER_CHARM_NAME}:secrets")
    juju.integrate(f"{CHARM_NAME}:pod-defaults", f"{RESOURCE_DISPATCHER_CHARM_NAME}:pod-defaults")

    # Wait for all charms to be active
    # Set successes to 1 due to the default being 3 to speed up tests
    juju.wait(jubilant.all_active, successes=1)


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


def test_configuration_requirer_charm(juju: jubilant.Juju):
    """Deploy test requirer charm, relate to Feast Integrator charm, and check logs."""
    juju.deploy(charm=charm_path(TESTER_CHARM_NAME))

    # Wait until charm is blocked due to missing relation
    juju.wait(lambda status: status.apps[TESTER_CHARM_NAME].is_blocked)

    # Relate to Feast Integrator charm
    juju.integrate(f"{CHARM_NAME}:feast-configuration", f"{TESTER_CHARM_NAME}:feast-configuration")

    # Requirer charm should be active
    juju.wait(jubilant.all_active, successes=2)

    # Fetch logs
    log_output = juju.debug_log(limit=1000)

    feast_yaml_text = extract_feast_yaml_from_logs(log_output)

    try:
        config = yaml.safe_load(feast_yaml_text)
    except yaml.YAMLError as e:
        pytest.fail(f"Failed to parse Feast configuration YAML:\n{feast_yaml_text}\n\n{e}")

    # Top-level keys
    expected_top_keys = {
        "project",
        "registry",
        "provider",
        "offline_store",
        "online_store",
        "entity_key_serialization_version",
    }
    assert set(config.keys()) == expected_top_keys

    # Registry block
    registry = config["registry"]
    assert registry["registry_type"] == "sql"
    assert isinstance(registry["path"], str)
    assert isinstance(registry["cache_ttl_seconds"], int)
    assert isinstance(registry["sqlalchemy_config_kwargs"], dict)
    assert registry["sqlalchemy_config_kwargs"] == {"echo": False, "pool_pre_ping": True}

    # Provider
    assert config["provider"] == "local"

    # Store blocks (check keys only, not sensitive values)
    for store_key in ["offline_store", "online_store"]:
        store = config[store_key]
        expected_store_keys = {"type", "host", "port", "database", "db_schema", "user", "password"}
        assert set(store.keys()) == expected_store_keys
        assert store["type"] == "postgres"

    # Entity key serialization version
    assert config["entity_key_serialization_version"] == 2


def charm_path(name: str) -> Path:
    """Return full absolute path to given charm located in the directory under the test file."""
    test_file_dir = Path(__file__).parent
    charm_dir = test_file_dir / name
    charms = list(charm_dir.glob(f"{name}_*.charm"))

    assert charms, f"{name}_*.charm not found in {charm_dir}"
    assert len(charms) == 1, (
        f"Multiple .charm files for {name} found in {charm_dir}, unsure which to use"
    )
    return charms[0].absolute()


def extract_feast_yaml_from_logs(log_output: str) -> str:
    """Extract the Feast YAML block from Juju debug-log output."""
    feast_yaml_lines = []
    recording = False

    for line in log_output.splitlines():
        if "feast configuration yaml:" in line:
            recording = True
            continue  # Skip the header line
        if recording:
            if line.startswith("INFO") or line.strip() == "":
                break
            feast_yaml_lines.append(line)

    if not feast_yaml_lines:
        raise ValueError("Feast configuration YAML block not found in logs")

    return "\n".join(feast_yaml_lines)
