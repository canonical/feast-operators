"""Chisme component to manage the requirer (in this case the sender) of pod-defaults relation."""

from pathlib import Path

from charmed_kubeflow_chisme.components.component import Component
from charms.resource_dispatcher.v0.resource_dispatcher import (
    KubernetesManifest,
    KubernetesManifestsRequirer,
)
from jinja2 import Template
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase

PODDEFAULT_FILE = "src/templates/feature_store_poddefault.yaml.j2"


class PodDefaultSenderComponent(Component):
    """Sends Feast configuration PodDefault via the kubernetes_manifest interface.

    A Component that renders and sends the feast configuration PodDefault over
    the kubernetes_manifest interface.

    Args:
        charm (CharmBase): the requirer charm
        context (dict[str, str]): the context of the PodDefault
        relation_name (str): name of the relation that uses the kubernetes_manifest interface
    """

    def __init__(
        self,
        charm: CharmBase,
        context: dict[str, str],
        relation_name: str = "pod-defaults",
    ):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.charm = charm
        self.context = context

        self.create_poddefault_requirer()
        self._events_to_observe = [
            self.charm.on["pod-defaults"].relation_created,
            self.charm.on["pod-defaults"].relation_broken,
        ]

    def create_poddefault_requirer(self):
        """Create the poddefault manifests and requirer."""
        # Load and render the PodDefault
        poddefault_template = Template(Path(PODDEFAULT_FILE).read_text())
        rendered_poddefault = poddefault_template.render(**self.context)
        self.manifests_items = [KubernetesManifest(rendered_poddefault)]

        # Create manifests requirer for PodDefault
        self.manifests_requirer = KubernetesManifestsRequirer(
            charm=self.charm,
            relation_name=self.relation_name,
            manifests_items=self.manifests_items,
        )

    def get_status(self) -> StatusBase:
        """Return this component's status based on the presence of the relation."""
        if not self.charm.model.get_relation(self.relation_name):
            # We need the user to do 'juju integrate'.
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")
        return ActiveStatus()
