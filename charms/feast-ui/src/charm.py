#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Feast UI charm."""

import logging
import tempfile
from typing import List

import ops
from charmed_kubeflow_chisme.components import (
    ContainerFileTemplate,
    SdiRelationBroadcasterComponent,
)
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import (
    LeadershipGateComponent,
)
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charms.kubeflow_dashboard.v0.kubeflow_dashboard_links import (
    DashboardLink,
    KubeflowDashboardLinksRequirer,
)
from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from lightkube.models.core_v1 import ServicePort
from ops import CharmBase, WaitingStatus

from components.pebble_component import FeastUIPebbleService
from components.store_configuration_reciver_component import (
    StoreConfigurationReceiverComponent,
)

logger = logging.getLogger(__name__)

HTTP_PORT = 8888
CONTAINER_NAME = "feast-ui-operator"
SERVICE_NAME = "feast-ui"
DEST_PATH = "/home/ubuntu/feature_store.yaml"
RELATION_NAME = "feast-configuration"

DASHBOARD_LINKS = [
    DashboardLink(
        text="Feast",
        link="/feast/",
        type="item",
        icon="device:data-usage",
        location="external",
    )
]


class FeastUICharm(CharmBase):
    """A Juju charm for Feast UI."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        # add links in kubeflow-dashboard sidebar
        self.kubeflow_dashboard_sidebar = KubeflowDashboardLinksRequirer(
            charm=self,
            relation_name="dashboard-links",
            dashboard_links=DASHBOARD_LINKS,
        )

        # Patch Kubernetes service to expose the HTTP port
        self.service_patcher = KubernetesServicePatch(
            self,
            [ServicePort(HTTP_PORT, name="http")],
            service_name=f"{self.model.app.name}",
        )

        self.charm_reconciler = CharmReconciler(self)

        # Leadership gate
        self.leadership_gate = self.charm_reconciler.add(
            component=LeadershipGateComponent(charm=self, name="leadership-gate"),
            depends_on=[],
        )

        self.ingress_relation = self.charm_reconciler.add(
            SdiRelationBroadcasterComponent(
                charm=self,
                name="relation:ingress",
                relation_name="ingress",
                data_to_send={
                    "prefix": "/feast",
                    "rewrite": "/",
                    "service": self.model.app.name,
                    "namespace": self.model.name,
                    "port": HTTP_PORT,
                },
            ),
            depends_on=[self.leadership_gate],
        )

        # Store config from relation
        self.store_configuration_receiver = self.charm_reconciler.add(
            component=StoreConfigurationReceiverComponent(charm=self, relation_name=RELATION_NAME),
            depends_on=[self.leadership_gate],
        )

        # Pebble service layer
        self.pebble_service_container = self.charm_reconciler.add(
            component=FeastUIPebbleService(
                charm=self,
                name="feast-ui-pebble-service",
                container_name=CONTAINER_NAME,
                service_name=SERVICE_NAME,
                files_to_push=self._generate_feature_store_file(),
            ),
            depends_on=[self.leadership_gate, self.store_configuration_receiver],
        )

        self.charm_reconciler.install_default_event_handlers()

    def _generate_feature_store_file(self) -> List[ContainerFileTemplate]:
        """Generate and return the feature_store.yaml to push to the container."""
        try:
            yaml_data = self.store_configuration_receiver.component.get_feature_store_yaml()
        except ErrorWithStatus as err:
            self.unit.status = err.status
            logger.info(f"Stopped early during feature store file generation: {err}")
            return []

        if not yaml_data:
            self.unit.status = WaitingStatus("feature_store.yaml is missing or empty")
            return []

        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".yaml") as f:
            f.write(yaml_data)
            path = f.name

        return [ContainerFileTemplate(source_template_path=path, destination_path=DEST_PATH)]


if __name__ == "__main__":  # pragma: nocover
    ops.main(FeastUICharm)
