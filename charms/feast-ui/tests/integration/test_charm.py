import logging
from pathlib import Path

import jubilant
import yaml

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
CHARM_NAME = METADATA["name"]

OFFLINE_STORE_APP = "offline-store"
ONLINE_STORE_APP = "online-store"
REGISTRY_APP = "registry"

ADMISSION_WEBHOOK = "admission-webhook"
RESOURCE_DISPATCHER = "resource-dispatcher"
METACONTROLLER = "metacontroller-operator"
FEAST_INTEGRATOR = "feast-integrator"
ISTIO_GATEWAY = "istio-gateway"
ISTIO_PILOT = "istio-pilot"


def test_deploy_charm(juju: jubilant.Juju, request):
    """Deploy Feast UI charm and all required dependencies."""
    juju.deploy(
        charm=request.config.getoption("--charm-path"),
        resources={"oci-image": IMAGE},
        trust=True,
    )

    juju.deploy(charm=charm_path_from_root(FEAST_INTEGRATOR))

    juju.wait(lambda status: status.apps[CHARM_NAME].is_blocked)

    # Deploy offline store and integrate
    juju.deploy(
        charm="postgresql-k8s",
        app=OFFLINE_STORE_APP,
        channel="14/stable",
        trust=True,
        config={"profile": "testing"},
    )
    juju.integrate(f"{FEAST_INTEGRATOR}:{OFFLINE_STORE_APP}", OFFLINE_STORE_APP)

    # Deploy online store and integrate
    juju.deploy(
        charm="postgresql-k8s",
        app=ONLINE_STORE_APP,
        channel="14/stable",
        trust=True,
        config={"profile": "testing"},
    )
    juju.integrate(f"{FEAST_INTEGRATOR}:{ONLINE_STORE_APP}", ONLINE_STORE_APP)

    # Deploy registry and integrate
    juju.deploy(
        charm="postgresql-k8s",
        app=REGISTRY_APP,
        channel="14/stable",
        trust=True,
        config={"profile": "testing"},
    )
    juju.integrate(f"{FEAST_INTEGRATOR}:{REGISTRY_APP}", REGISTRY_APP)

    # Deploy supporting services
    juju.deploy(charm=METACONTROLLER, channel="latest/edge", trust=True)
    juju.deploy(charm=RESOURCE_DISPATCHER, channel="latest/edge", trust=True)
    juju.deploy(charm=ADMISSION_WEBHOOK, channel="latest/edge", trust=True)

    # Integrate secrets and pod-defaults
    juju.integrate(f"{FEAST_INTEGRATOR}:secrets", f"{RESOURCE_DISPATCHER}:secrets")
    juju.integrate(f"{FEAST_INTEGRATOR}:pod-defaults", f"{RESOURCE_DISPATCHER}:pod-defaults")

    # Integrate feast-configuration
    juju.integrate(f"{FEAST_INTEGRATOR}:feast-configuration", f"{CHARM_NAME}:feast-configuration")

    juju.wait(jubilant.all_active, successes=2)


def test_ingress_setup(juju: jubilant.Juju):
    """Deploy Istio and relate with Feast UI ingress interface."""
    juju.deploy(
        charm=ISTIO_GATEWAY,
        channel="latest/edge",
        config={"kind": "ingress"},
        trust=True,
    )

    juju.deploy(
        charm=ISTIO_PILOT,
        channel="latest/edge",
        config={"default-gateway": ISTIO_GATEWAY},
        trust=True,
    )

    juju.integrate(ISTIO_PILOT, ISTIO_GATEWAY)

    juju.wait(lambda status: status.apps[ISTIO_GATEWAY].is_active)
    juju.wait(lambda status: status.apps[ISTIO_PILOT].is_active)

    juju.integrate(f"{ISTIO_PILOT}:ingress", f"{CHARM_NAME}:ingress")

    juju.wait(jubilant.all_active)


def charm_path_from_root(charm_dir_name: str) -> Path:
    """Return absolute path to the built charm file for a given charm directory name."""
    repo_root = Path(__file__).resolve().parents[4]
    charm_dir = repo_root / "charms" / charm_dir_name

    charms = list(charm_dir.glob(f"{charm_dir_name}_*.charm"))
    assert charms, f"No .charm file found for {charm_dir_name} in {charm_dir}"
    assert len(charms) == 1, f"Multiple .charm files found for {charm_dir_name} in {charm_dir}"
    return charms[0].absolute()
