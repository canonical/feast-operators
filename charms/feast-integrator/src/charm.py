#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Feast Integrator charm.

Feast Integrator charm connects the Feast components.
The charm integrates with the registry, online store, and offline store databases.
It then creates the feature store configuration file with the databases connection details.
"""

import logging
from pathlib import Path

import ops
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import (
    LeadershipGateComponent,
)

from components.database_requirer_component import PostgresRequirerComponent
from components.poddefault_sender_component import PodDefaultSenderComponent
from components.secret_sender_component import (
    FeastSecretSenderComponent,
    FeastSecretSenderInputs,
)
from components.store_configuration_sender_component import (
    StoreConfigurationSenderComponent,
    StoreConfigurationSenderInputs,
)

logger = logging.getLogger(__name__)

PODDEFAULT_FILE_PATH = Path("src/templates/feature_store_poddefault.yaml.j2")
SECRET_FILE_PATH = Path("src/templates/feature_store_secret.yaml.j2")
SECRET_NAME = "feature-store-yaml"


class FeastIntegratorCharm(ops.CharmBase):
    """A Juju charm for Feast Integrator."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.charm_reconciler = CharmReconciler(self)
        self._namespace = self.model.name

        self.leadership_gate = self.charm_reconciler.add(
            component=LeadershipGateComponent(
                charm=self,
                name="leadership-gate",
            ),
            depends_on=[],
        )

        self.offline_store_requirer = self.charm_reconciler.add(
            component=PostgresRequirerComponent(
                charm=self, relation_name="offline-store", database_name="offline_store"
            ),
            depends_on=[self.leadership_gate],
        )

        self.online_store_requirer = self.charm_reconciler.add(
            component=PostgresRequirerComponent(
                charm=self, relation_name="online-store", database_name="online_store"
            ),
            depends_on=[self.leadership_gate],
        )

        self.registry_requirer = self.charm_reconciler.add(
            component=PostgresRequirerComponent(
                charm=self, relation_name="registry", database_name="registry"
            ),
            depends_on=[self.leadership_gate],
        )

        self.secret_sender = self.charm_reconciler.add(
            component=FeastSecretSenderComponent(
                charm=self,
                relation_name="secrets",
                path_to_manifest=SECRET_FILE_PATH,
                inputs_getter=lambda: FeastSecretSenderInputs(
                    context={
                        **self.offline_store_requirer.component.fetch_relation_data(),
                        **self.online_store_requirer.component.fetch_relation_data(),
                        **self.registry_requirer.component.fetch_relation_data(),
                        **{"secret_name": SECRET_NAME},
                    }
                ),
            ),
            depends_on=[
                self.offline_store_requirer,
                self.online_store_requirer,
                self.registry_requirer,
            ],
        )

        self.poddefault_sender = self.charm_reconciler.add(
            component=PodDefaultSenderComponent(
                charm=self,
                context={"app_name": self.app.name, "secret_name": SECRET_NAME},
                path_to_manifest=PODDEFAULT_FILE_PATH,
                relation_name="pod-defaults",
            ),
            depends_on=[self.secret_sender],
        )

        self.store_configuration_sender = self.charm_reconciler.add(
            component=StoreConfigurationSenderComponent(
                charm=self,
                inputs_getter=lambda: StoreConfigurationSenderInputs(
                    context={
                        **self.offline_store_requirer.component.fetch_relation_data(),
                        **self.online_store_requirer.component.fetch_relation_data(),
                        **self.registry_requirer.component.fetch_relation_data(),
                    }
                ),
            ),
            depends_on=[
                self.offline_store_requirer,
                self.online_store_requirer,
                self.registry_requirer,
            ],
        )

        self.charm_reconciler.install_default_event_handlers()


if __name__ == "__main__":  # pragma: nocover
    ops.main(FeastIntegratorCharm)
