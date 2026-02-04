import logging
from pathlib import Path

import jubilant
import lightkube
import pytest
import tenacity
import yaml
from charmed_kubeflow_chisme.testing import (
    CharmSpec,
    assert_path_reachable_through_ingress,
    assert_security_context,
    generate_container_securitycontext_map,
    get_pod_names,
)
from charms_dependencies import (
    ADMISSION_WEBHOOK,
    FEAST_INTEGRATOR,
    ISTIO_BEACON_K8S,
    ISTIO_INGRESS_K8S,
    ISTIO_K8S,
    METACONTROLLER,
    OFFLINE_STORE,
    ONLINE_STORE,
    REGISTRY,
    RESOURCE_DISPATCHER,
)

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
CHARM_NAME = METADATA["name"]
IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
CONTAINERS_SECURITY_CONTEXT_MAP = generate_container_securitycontext_map(METADATA)
FEAST_DBS_NAMES = ["offline-store", "online-store", "registry"]
HTTP_PATH = "/feast/"
ISTIO_INGRESS_ROUTE_ENDPOINT = "istio-ingress-route"
RETRY_FOR_THREE_MINUTES = tenacity.Retrying(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=15),
    stop=tenacity.stop_after_delay(180),
    reraise=True,
)
SERVICE_MESH_ENDPOINT = "service-mesh"


def charm_path_from_root(charm_dir_name: str) -> Path:
    """Return absolute path to the built charm file for a given charm directory name."""
    repo_root = Path(__file__).resolve().parents[4]
    charm_dir = repo_root / "charms" / charm_dir_name

    charms = list(charm_dir.glob(f"{charm_dir_name}_*.charm"))
    assert charms, f"No .charm file found for {charm_dir_name} in {charm_dir}"
    assert len(charms) == 1, f"Multiple .charm files found for {charm_dir_name} in {charm_dir}"
    return charms[0].absolute()


@pytest.fixture(scope="session")
def lightkube_client() -> lightkube.Client:
    client = lightkube.Client(field_manager=CHARM_NAME)
    return client


def test_deploy_charm(juju: jubilant.Juju, request: pytest.FixtureRequest):
    """Deploy Feast UI charm and required dependencies."""
    juju.deploy(
        charm=request.config.getoption("--charm-path"),
        resources={"oci-image": IMAGE},
        trust=True,
    )

    juju.deploy(charm=charm_path_from_root(FEAST_INTEGRATOR.charm))

    logger.info(f"Waiting for {CHARM_NAME} to be blocked..")
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
    logger.info("Waiting for DB charms to be active..")
    juju.wait(lambda status: jubilant.all_active(status, FEAST_DBS_NAMES), successes=1)

    for app in FEAST_DBS_NAMES:
        juju.integrate(f"{FEAST_INTEGRATOR.charm}:{app}", app)

    # Deploy metacontroller due to resource-dispatcher depending on the DecoratorController CRD
    juju.deploy(
        charm=METACONTROLLER.charm,
        channel="latest/edge",
        trust=True,
    )

    # Wait for metacontroller to be active
    logger.info(f"Waiting for {METACONTROLLER.charm} charm to be active..")
    juju.wait(lambda status: status.apps[METACONTROLLER.charm].is_active)

    # Deploy admission-webhook and resource-dispatcher
    for component in [RESOURCE_DISPATCHER, ADMISSION_WEBHOOK]:
        juju.deploy(
            charm=component.charm,
            channel=component.channel,
            trust=component.trust,
        )

    # Wait for dependency charms to be active
    logger.info("Waiting for dependency charms to be active..")
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

    logger.info("Waiting for all charms to be active..")
    juju.wait(jubilant.all_active, successes=1)


def test_ambient_mesh_and_ingress_setup(juju: jubilant.Juju):
    """Deploy Istio in ambient mode and integrate it with all charms and for the UI's ingress."""
    # integrating charms that provide the ambient-mode service mesh and the ingress:
    for charm in (ISTIO_K8S, ISTIO_BEACON_K8S, ISTIO_INGRESS_K8S):
        juju.deploy(
            charm=charm.charm,
            channel=charm.channel,
            config=charm.config,
            trust=charm.trust,
        )
        juju.wait(lambda status: status.apps[charm.charm].is_active)

    # integrating the UI with the service mesh:
    juju.integrate(
        f"{ISTIO_BEACON_K8S.charm}:{SERVICE_MESH_ENDPOINT}",
        f"{CHARM_NAME}:{SERVICE_MESH_ENDPOINT}",
    )
    logger.info("Waiting for the UI to be active after entering the service mesh...")
    juju.wait(lambda status: status.apps[CHARM_NAME].is_active)

    # integrating the UI with the ingress:
    juju.integrate(
        f"{ISTIO_INGRESS_K8S.charm}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
        f"{CHARM_NAME}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
    )
    logger.info("Waiting for the UI to be active after integrating it with the ingress...")
    juju.wait(lambda status: status.apps[CHARM_NAME].is_active)


async def test_feast_ui_ingress_accessible(juju: jubilant.Juju):
    """Ensure that Feast UI is reachable through the Ingress."""
    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            await assert_path_reachable_through_ingress(
                http_path=HTTP_PATH,
                namespace=juju.model,
                expected_content_type="text/html",
                expected_response_text="Feast",
            )


@pytest.mark.parametrize("container_name", list(CONTAINERS_SECURITY_CONTEXT_MAP.keys()))
def test_container_security_context(
    juju: jubilant.Juju,
    lightkube_client: lightkube.Client,
    container_name: str,
):
    """Test container security context is correctly set.

    Verify that container spec defines the security context with correct
    user ID and group ID.
    """
    pod_name = get_pod_names(juju.model, CHARM_NAME)[0]
    assert_security_context(
        lightkube_client,
        pod_name,
        container_name,
        CONTAINERS_SECURITY_CONTEXT_MAP,
        juju.model,
    )
