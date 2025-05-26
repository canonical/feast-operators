import logging
from pathlib import Path

import jubilant
import yaml

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
CHARM_NAME = METADATA["name"]

OFFLINE_STORE_APP_NAME = "offline-store"
ONLINE_STORE_APP_NAME = "online-store"
REGISTRY_APP_NAME = "registry"

ADMISSION_WEBHOOK_CHARM_NAME = "admission-webhook"
RESOURCE_DISPATCHER_CHARM_NAME = "resource-dispatcher"
METACONTROLLER_CHARM_NAME = "metacontroller-operator"
FEAST_INTEGRATOR_CHARM_NAME = "feast-integrator"


def test_deploy_charm(juju: jubilant.Juju, request):
    """Test deploy the charm and its dependencies go to active."""
    juju.deploy(
        charm=request.config.getoption("--charm-path"),
        resources={"oci-image": IMAGE},
    )

    juju.deploy(charm=charm_path_from_root(FEAST_INTEGRATOR_CHARM_NAME))

    juju.wait(lambda status: status.apps[CHARM_NAME].is_blocked)

    for db_type in [OFFLINE_STORE_APP_NAME, ONLINE_STORE_APP_NAME, REGISTRY_APP_NAME]:
        juju.deploy(
            charm="postgresql-k8s",
            app=db_type,
            channel="14/stable",
            trust=True,
            config={"profile": "testing"},
        )
        juju.integrate(f"{FEAST_INTEGRATOR_CHARM_NAME}:{db_type}", db_type)

    juju.deploy(
        charm=METACONTROLLER_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    juju.deploy(
        charm=RESOURCE_DISPATCHER_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    juju.integrate(
        f"{FEAST_INTEGRATOR_CHARM_NAME}:secrets",
        f"{RESOURCE_DISPATCHER_CHARM_NAME}:secrets",
    )
    juju.integrate(
        f"{FEAST_INTEGRATOR_CHARM_NAME}:pod-defaults",
        f"{RESOURCE_DISPATCHER_CHARM_NAME}:pod-defaults",
    )

    juju.deploy(
        charm=ADMISSION_WEBHOOK_CHARM_NAME,
        channel="latest/edge",
        trust=True,
    )

    juju.integrate(
        f"{FEAST_INTEGRATOR_CHARM_NAME}:feast-configuration",
        f"{CHARM_NAME}:feast-configuration",
    )

    juju.wait(jubilant.all_active, successes=2)

def charm_path_from_root(charm_dir_name: str) -> Path:
    """Return absolute path to the built charm file for a given charm directory name."""
    # Step up from `charms/feast-ui/tests/integration/` → to repo root
    repo_root = Path(__file__).resolve().parents[4]
    charm_dir = repo_root / "charms" / charm_dir_name

    # Find the built charm file (*.charm) inside that directory
    charms = list(charm_dir.glob(f"{charm_dir_name}_*.charm"))

    assert charms, f"No .charm file found for {charm_dir_name} in {charm_dir}"
    assert len(charms) == 1, (
        f"Multiple charm files found for {charm_dir_name} in {charm_dir}, "
        "please remove duplicates"
    )
    return charms[0].absolute()
