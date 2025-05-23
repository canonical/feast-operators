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

    juju.deploy(
        charm=FEAST_INTEGRATOR_CHARM_NAME,
        channel="latest/edge",
    )

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


# def test_feast_ui_has_feature_store_file(juju: jubilant.Juju):
#     """Verify the feast-ui container has /home/ubuntu/feature_store.yaml."""
#     unit_name = f"{CHARM_NAME}/0"
#     container_name = "feast-ui-operator"

#     for attempt in RETRY:
#         with attempt:
#             output = juju.ssh(
#                 target=unit_name,
#                 container=container_name,
#                 command="cat",
#                 args="/home/ubuntu/feature_store.yaml",
#             )
#             assert "registry:" in output,
# "Expected 'registry:' key in feature_store.yaml content"


# # Helpers

# def charm_path(name: str) -> Path:
#     """Return full absolute path to given charm located in the directory under the test file."""
#     test_file_dir = Path(__file__).parent
#     charm_dir = test_file_dir / name
#     charms = list(charm_dir.glob(f"{name}_*.charm"))

#     assert charms, f"{name}_*.charm not found in {charm_dir}"
#     assert len(charms) == 1, (
#         f"Multiple .charm files for {name} found in {charm_dir}, unsure which to use"
#     )
#     return charms[0].absolute()
