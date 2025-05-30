import logging
from pathlib import Path

import jubilant
import lightkube
import pytest
import requests
import tenacity
import yaml
from charms_dependencies import (
    ADMISSION_WEBHOOK,
    FEAST_INTEGRATOR,
    ISTIO_GATEWAY,
    ISTIO_PILOT,
    METACONTROLLER,
    OFFLINE_STORE,
    ONLINE_STORE,
    REGISTRY,
    RESOURCE_DISPATCHER,
)
from lightkube.resources.core_v1 import Service

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
CHARM_NAME = METADATA["name"]
FEAST_DBS_NAMES = ["offline-store", "online-store", "registry"]


@pytest.fixture(scope="session")
def lightkube_client() -> lightkube.Client:
    client = lightkube.Client(field_manager=CHARM_NAME)
    return client


def test_deploy_charm(juju: jubilant.Juju, request):
    """Deploy Feast UI charm and required dependencies."""
    juju.deploy(
        charm=request.config.getoption("--charm-path"),
        resources={"oci-image": IMAGE},
        trust=True,
    )

    juju.deploy(charm=charm_path_from_root(FEAST_INTEGRATOR.charm))

    juju.wait(lambda status: status.apps[CHARM_NAME].is_blocked, successes=1)

    for spec, app in zip(
        [OFFLINE_STORE, ONLINE_STORE, REGISTRY],
        FEAST_DBS_NAMES,
    ):
        juju.deploy(
            charm=spec.charm,
            app=app,
            channel=spec.channel,
            trust=spec.trust,
            config=spec.config,
        )

    # Wait for Postgresql charms to be active
    juju.wait(lambda status: jubilant.all_active(status, FEAST_DBS_NAMES), successes=1)

    for app in FEAST_DBS_NAMES:
        juju.integrate(f"{FEAST_INTEGRATOR.charm}:{app}", app)

    for component in [METACONTROLLER, RESOURCE_DISPATCHER, ADMISSION_WEBHOOK]:
        juju.deploy(
            charm=component.charm,
            channel=component.channel,
            trust=component.trust,
        )

    # Wait for dependency charms to be active
    juju.wait(
        lambda status: jubilant.all_active(
            status,
            [
                METACONTROLLER.charm,
                RESOURCE_DISPATCHER.charm,
                ADMISSION_WEBHOOK.charm,
            ],
        ),
        successes=1,
    )

    # Relate to resource-dispatcher
    juju.integrate(f"{FEAST_INTEGRATOR.charm}:secrets", f"{RESOURCE_DISPATCHER.charm}:secrets")
    juju.integrate(
        f"{FEAST_INTEGRATOR.charm}:pod-defaults",
        f"{RESOURCE_DISPATCHER.charm}:pod-defaults",
    )

    # Relate to feast-integrator
    juju.integrate(
        f"{FEAST_INTEGRATOR.charm}:feast-configuration",
        f"{CHARM_NAME}:feast-configuration",
    )

    juju.wait(jubilant.all_active, successes=1)


def test_ingress_setup(juju: jubilant.Juju):
    """Deploy Istio and relate it with Feast UI ingress interface."""
    for spec in [ISTIO_GATEWAY, ISTIO_PILOT]:
        juju.deploy(
            charm=spec.charm,
            channel=spec.channel,
            config=spec.config,
            trust=spec.trust,
        )

    juju.integrate(ISTIO_PILOT.charm, ISTIO_GATEWAY.charm)
    juju.wait(lambda status: status.apps[ISTIO_GATEWAY.charm].is_active, successes=1)
    juju.wait(lambda status: status.apps[ISTIO_PILOT.charm].is_active, successes=1)

    juju.integrate(f"{ISTIO_PILOT.charm}:ingress", f"{CHARM_NAME}:ingress")
    juju.wait(jubilant.all_active, successes=1)


def charm_path_from_root(charm_dir_name: str) -> Path:
    """Return absolute path to the built charm file for a given charm directory name."""
    repo_root = Path(__file__).resolve().parents[4]
    charm_dir = repo_root / "charms" / charm_dir_name

    charms = list(charm_dir.glob(f"{charm_dir_name}_*.charm"))
    assert charms, f"No .charm file found for {charm_dir_name} in {charm_dir}"
    assert len(charms) == 1, f"Multiple .charm files found for {charm_dir_name} in {charm_dir}"
    return charms[0].absolute()


RETRY_FOR_THREE_MINUTES = tenacity.Retrying(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=15),
    stop=tenacity.stop_after_delay(180),
    reraise=True,
)


def get_ingress_url(lightkube_client, model_name: str) -> str:
    """Return external ingress URL for the Istio Gateway."""
    svc = lightkube_client.get(Service, "istio-ingressgateway-workload", namespace=model_name)
    ingress = svc.status.loadBalancer.ingress[0]
    if ingress.ip:
        return f"http://{ingress.ip}.nip.io"
    elif ingress.hostname:
        return f"http://{ingress.hostname}"
    else:
        raise RuntimeError("No IP or hostname found in ingress service")


def test_feast_ui_ingress_accessible(juju: jubilant.Juju, lightkube_client):
    """Ensure that Feast UI is reachable through Ingress at /feast."""
    base_url = get_ingress_url(lightkube_client, juju.model)
    feast_url = f"{base_url}/feast/"

    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            response = requests.get(feast_url, timeout=10)
            assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
            assert "Feast" in response.text or len(response.text) > 0, "Expected Feast UI content"
