import logging
from pathlib import Path

import jubilant
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

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
CHARM_NAME = METADATA["name"]
FEAST_DBS_NAMES = ["offline-store", "online-store", "registry"]


def test_deploy_charm(juju: jubilant.Juju, request):
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

    logger.info("Waiting for istio charms to be active..")
    juju.wait(lambda status: status.apps[ISTIO_GATEWAY.charm].is_active, successes=1)
    juju.wait(lambda status: status.apps[ISTIO_PILOT.charm].is_active, successes=1)

    juju.integrate(f"{ISTIO_PILOT.charm}:ingress", f"{CHARM_NAME}:ingress")
    logger.info("Waiting for all charms to be active..")
    juju.wait(jubilant.all_active, successes=1)


def charm_path_from_root(charm_dir_name: str) -> Path:
    """Return absolute path to the built charm file for a given charm directory name."""
    repo_root = Path(__file__).resolve().parents[4]
    charm_dir = repo_root / "charms" / charm_dir_name

    charms = list(charm_dir.glob(f"{charm_dir_name}_*.charm"))
    assert charms, f"No .charm file found for {charm_dir_name} in {charm_dir}"
    assert len(charms) == 1, f"Multiple .charm files found for {charm_dir_name} in {charm_dir}"
    return charms[0].absolute()
