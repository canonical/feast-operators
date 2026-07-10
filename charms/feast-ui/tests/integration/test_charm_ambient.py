import logging
from pathlib import Path

import jubilant
import lightkube
import pytest
import tenacity
import yaml
from charmed_kubeflow_chisme.testing import (
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
from lightkube.generic_resource import create_namespaced_resource
from requests import get

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

# A second istio-ingress-k8s instance used to verify multiple-ingress support.
SECOND_INGRESS_APP = "istio-ingress-k8s-alt"
# Name of the HTTPRoute submitted by feast-ui (see AmbientIngressRequirerComponent).
INGRESS_ROUTE_NAME = "http-route"
# Gateway listener section for cleartext HTTP on port 80.
HTTP_SECTION_NAME = "http-80"
# Gateway API generic resources, resolved at runtime via lightkube.
HTTPROUTE_RESOURCE = create_namespaced_resource(
    "gateway.networking.k8s.io", "v1", "HTTPRoute", "httproutes"
)
GATEWAY_RESOURCE = create_namespaced_resource(
    "gateway.networking.k8s.io", "v1", "Gateway", "gateways"
)


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
    # deploying charms that provide the ambient-mode service mesh and the ingress:
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


def get_ingress_url(k8s_client, model_name: str) -> str:
    """Return external ingress URL for the Istio Gateway."""
    ingress_service_name = "istio-ingress-k8s-istio"

    ingress_service = k8s_client.get(
        lightkube.resources.core_v1.Service, name=ingress_service_name, namespace=model_name
    )

    assert ingress_service.status.loadBalancer.ingress, (
        f"Service {ingress_service_name} in namespace {model_name} does not have a LoadBalancer IP"
    )

    return f"http://{ingress_service.status.loadBalancer.ingress[0].ip}"


def test_feast_ui_ingress_accessible(lightkube_client: lightkube.Client, juju: jubilant.Juju):
    """Ensure that Feast UI is reachable through the Ingress."""
    ingress_url = get_ingress_url(lightkube_client, juju.model)
    feast_url = f"{ingress_url}{HTTP_PATH}"

    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            response = get(feast_url, timeout=10)
            assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
            assert "Feast" in response.text or len(response.text) > 0, "Expected Feast UI content"


def test_deploy_and_relate_second_ingress(juju: jubilant.Juju):
    """Deploy a second istio-ingress-k8s and relate it to feast-ui.

    feast-ui must accept more than one istio-ingress-route relation without erroring,
    so it should remain active after the second ingress is related.
    """
    juju.deploy(
        charm=ISTIO_INGRESS_K8S.charm,
        app=SECOND_INGRESS_APP,
        channel=ISTIO_INGRESS_K8S.channel,
        trust=ISTIO_INGRESS_K8S.trust,
    )
    logger.info(f"Waiting for {SECOND_INGRESS_APP} to be active..")
    juju.wait(lambda status: status.apps[SECOND_INGRESS_APP].is_active)

    juju.integrate(
        f"{SECOND_INGRESS_APP}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
        f"{CHARM_NAME}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
    )
    logger.info("Waiting for the UI to be active after relating the second ingress...")
    juju.wait(
        lambda status: status.apps[CHARM_NAME].is_active
        and status.apps[SECOND_INGRESS_APP].is_active
    )


def test_httproute_attached_to_second_gateway(
    lightkube_client: lightkube.Client, juju: jubilant.Juju
):
    """Verify the HTTPRoute for the second ingress is created and bound to its Gateway.

    The istio-ingress-k8s charm names each route
    ``{source_app}-{route_name}-httproute-{section}-{ingress_app}`` and binds it to a
    Gateway named after the ingress application via ``parentRefs``. We assert that the
    route created for the second ingress is attached to the *second* Gateway (not the
    first) and routes the feast path to the feast-ui backend.
    """
    namespace = juju.model

    expected_route_name = (
        f"{CHARM_NAME}-{INGRESS_ROUTE_NAME}-httproute-{HTTP_SECTION_NAME}-{SECOND_INGRESS_APP}"
    )

    # The second Gateway should exist, named after the second ingress application.
    lightkube_client.get(GATEWAY_RESOURCE, name=SECOND_INGRESS_APP, namespace=namespace)

    # Retry to give the ingress charm time to reconcile the HTTPRoute resources.
    httproute = None
    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            httproute = lightkube_client.get(
                HTTPROUTE_RESOURCE, name=expected_route_name, namespace=namespace
            )

    parent_refs = httproute.spec["parentRefs"]
    assert len(parent_refs) == 1
    # The route must be attached to the SECOND gateway, not the first.
    assert parent_refs[0]["name"] == SECOND_INGRESS_APP
    assert parent_refs[0]["sectionName"] == HTTP_SECTION_NAME

    # And it must route the feast path to the feast-ui backend.
    rule = httproute.spec["rules"][0]
    assert rule["matches"][0]["path"]["value"] == HTTP_PATH
    assert rule["backendRefs"][0]["name"] == CHARM_NAME


def test_feast_ui_ingress_accessible_after_second_ingress(
    lightkube_client: lightkube.Client, juju: jubilant.Juju
):
    """Ensure Feast UI is still reachable through the ingress after adding a second ingress."""
    ingress_url = get_ingress_url(lightkube_client, juju.model)
    feast_url = f"{ingress_url}{HTTP_PATH}"

    for attempt in RETRY_FOR_THREE_MINUTES:
        with attempt:
            response = get(feast_url, timeout=10)
            assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
            assert "Feast" in response.text or len(response.text) > 0, "Expected Feast UI content"


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
