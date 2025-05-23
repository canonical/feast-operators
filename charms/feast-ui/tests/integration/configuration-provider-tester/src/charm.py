#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Feast UI charm."""

import logging
import tempfile

import ops
from charmed_kubeflow_chisme.components import ContainerFileTemplate
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import LeadershipGateComponent
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from components.pebble_component import FeastUIPebbleService
from components.store_configuration_reciver_component import StoreConfigurationReceiverComponent
from lightkube.models.core_v1 import ServicePort
from ops.main import main
from ops.model import WaitingStatus

HTTP_PORT = 8888
PEBBLE_CONTAINER_NAME = "feast-ui-operator"
PEBBLE_SERVICE_NAME = "feast-ui"
FEATURE_STORE_DEST_PATH = "/home/ubuntu/feature_store.yaml"
RELATION_NAME = "feast-configuration"

logger = logging.getLogger(__name__)


class FeastUICharm(ops.CharmBase):
    """A Juju charm for deploying Feast UI."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        # Patch Kubernetes service for networking
        self.service_patcher = KubernetesServicePatch(
            self,
            [ServicePort(HTTP_PORT, name="http")],
            service_name=self.model.app.name,
        )

        self.charm_reconciler = CharmReconciler(self)

        # Component: Leadership gate
        self.leadership_gate = self.charm_reconciler.add(
            LeadershipGateComponent(
                charm=self,
                name="leadership-gate",
            )
        )

        # Component: Receives config over relation
        self.store_configuration_receiver = self.charm_reconciler.add(
            StoreConfigurationReceiverComponent(
                charm=self,
                relation_name=RELATION_NAME,
            ),
            depends_on=[self.leadership_gate],
        )

        # Component: Pebble service
        self.pebble_service_container = self.charm_reconciler.add(
            FeastUIPebbleService(
                charm=self,
                name="feast-ui-pebble-service",
                container_name=PEBBLE_CONTAINER_NAME,
                service_name=PEBBLE_SERVICE_NAME,
                files_to_push=self._generate_feature_store_file(),
            ),
            depends_on=[self.leadership_gate, self.store_configuration_receiver],
        )

        self.charm_reconciler.install_default_event_handlers()

    def _generate_feature_store_file(self) -> list[ContainerFileTemplate]:
        """Generate a temporary file with `feature_store.yaml` content pushed to the container."""
        try:
            yaml_data = self.store_configuration_receiver.component.get_feature_store_yaml()
        except ErrorWithStatus as err:
            self.unit.status = err.status
            logger.info(f"Aborting config push: {err}")
            return []

        if not yaml_data:
            self.unit.status = WaitingStatus("feature_store.yaml is missing or empty")
            return []

        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".yaml") as temp_file:
            temp_file.write(yaml_data)
            temp_file_path = temp_file.name

        return [
            ContainerFileTemplate(
                source_template_path=temp_file_path,
                destination_path=FEATURE_STORE_DEST_PATH,
            )
        ]


if __name__ == "__main__":  # pragma: nocover
    main(FeastUICharm)
