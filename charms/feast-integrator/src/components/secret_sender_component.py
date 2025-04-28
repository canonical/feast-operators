"""Chisme component to manage the requirer (in this case the sender) of secrets relation."""

import dataclasses
import logging
from pathlib import Path

from charmed_kubeflow_chisme.components.component import Component
from charms.resource_dispatcher.v0.resource_dispatcher import (
    KubernetesManifest,
    KubernetesManifestRequirerWrapper,
)
from jinja2 import Template
from ops import ActiveStatus, BlockedStatus, CharmBase, ErrorStatus, StatusBase, WaitingStatus

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class FeastSecretSenderInputs:
    """Defines the required inputs for FeastSecretSenderComponent."""

    context: dict


class FeastSecretSenderComponent(Component):
    """Sends Feast Secret via the kubernetes_manifest interface.

    A Component that renders and sends the feast configuration file
    as a K8s Secret over the kubernetes_manifest interface.

    Args:
        charm(CharmBase): the requirer charm
        path_to_manifest(Path): Path to the manifest to render
        relation_name(str, Optional): name of the relation that uses
        the kubernetes_manifest interface
    """

    def __init__(
        self,
        charm: CharmBase,
        path_to_manifest: Path,
        relation_name: str = "secrets",
        *args,
        **kwargs,
    ):
        super().__init__(charm, relation_name, *args, **kwargs)
        self.charm = charm
        self.path_to_manifest = path_to_manifest
        self.relation_name = relation_name

        self._manifests_requirer_wrapper = KubernetesManifestRequirerWrapper(
            charm=self.charm, relation_name=self.relation_name
        )

        self._events_to_observe = [
            self.charm.on[relation_name].relation_created,
            self.charm.on[relation_name].relation_broken,
        ]

    def render_manifests(self) -> str:
        """Render Feast configuration file and embed it into a K8s Secret manifest."""
        # Get databases context
        context = self._inputs_getter().context

        # Load and render the Feast config template
        config_template = Template(self.path_to_manifest.read_text())
        rendered_secret = config_template.render(context)

        return rendered_secret

    def send_configuration(self):
        """Render the manifests and send the configuration over the relation."""
        rendered_configuration = self.render_manifests()
        secret_manifests = [KubernetesManifest(rendered_configuration)]
        self._manifests_requirer_wrapper.send_data(secret_manifests)

    def get_status(self) -> StatusBase:
        """Return this component's status based on the relation."""
        if not self.charm.model.get_relation(self.relation_name):
            # We need the user to do 'juju integrate'.
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")
        # validate configuration availability
        try:
            self._inputs_getter()
        except Exception as err:
            return WaitingStatus(f"Configuration not provided: {err}")
        try:
            self.send_configuration()
        except Exception as err:
            return ErrorStatus(f"Failed to send data on {self.relation_name} relation: {err}")
        return ActiveStatus()
