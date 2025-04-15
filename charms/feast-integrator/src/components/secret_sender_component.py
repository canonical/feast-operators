import base64
import dataclasses
import logging
from pathlib import Path

from charmed_kubeflow_chisme.components.component import Component
from charms.resource_dispatcher.v0.resource_dispatcher import (
    KubernetesManifest,
    KubernetesManifestRequirerWrapper,
)
from jinja2 import Template
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus

CONFIG_FILE = "src/templates/feature_store.yaml.j2"
SECRET_FILE = "src/templates/feature_store_secret.yaml.j2"

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class FeastSecretSenderInputs:
    """Defines the required inputs for FeastSecretSenderComponent."""

    context: dict


class FeastSecretSenderComponent(Component):
    """A Component that renders and sends the feast configuration file
    as a K8s Secret over the kubernetes_manifest interface.

    Args:
        charm(CharmBase): the requirer charm
        context(dict[str, str]): the context of the feast configuration
        relation_name(str, Optional): name of the relation that uses
        the kubernetes_manifest interface
    """

    def __init__(self, charm: CharmBase, relation_name: str = "secrets", *args, **kwargs):
        super().__init__(charm, relation_name, *args, **kwargs)
        self.charm = charm
        self.relation_name = relation_name

        self._manifests_requirer_wrapper = KubernetesManifestRequirerWrapper(
            charm=self.charm, relation_name=self.relation_name
        )

        self._events_to_observe = [
            self.charm.on["secrets"].relation_created,
            self.charm.on["secrets"].relation_broken,
        ]

    def render_manifests(self) -> str:
        """
        Render Feast configuration file and embed it into a K8s Secret manifest.
        """
        # Get databases context
        context = self._inputs_getter().context

        # Load and render the Feast config template
        config_template = Template(Path(CONFIG_FILE).read_text())
        rendered_config = config_template.render(context)

        # Base64 encode the rendered config
        rendered_config_b64 = base64.b64encode(rendered_config.encode("utf-8")).decode("utf-8")

        # Load and render the Kubernetes Secret template
        secret_template = Template(Path(SECRET_FILE).read_text())
        rendered_secret = secret_template.render(
            {"feature_store_yaml_b64": rendered_config_b64, "secret_name": context["secret_name"]}
        )

        return rendered_secret

    def send_configuration(self):
        """Render the manifests and send the configuration over the relation."""
        rendered_configuration = self.render_manifests()
        secret_manifests = [KubernetesManifest(rendered_configuration)]
        self._manifests_requirer_wrapper.send_data(secret_manifests)

    def get_status(self) -> StatusBase:
        """Return this component's status based on the presence of the relation and
        sending the configuration.
        """
        if not self.charm.model.get_relation(self.relation_name):
            # We need the user to do 'juju integrate'.
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")
        # validate configuration availability
        try:
            self._inputs_getter()
        except Exception as err:
            return WaitingStatus(f"Database Configuration not provided: {err}")
        self.send_configuration()
        return ActiveStatus()
