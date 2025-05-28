# Copyright 2025 Canonical Ltd.

"""Component to receive and validate feature store configuration via a relation."""

import logging
from typing import Optional

from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charms.feast_integrator.v0.feast_store_configuration import (
    FeastStoreConfigurationDataInvalidError,
    FeastStoreConfigurationRelationDataMissingError,
    FeastStoreConfigurationRelationError,
    FeastStoreConfigurationRequirer,
)
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus

logger = logging.getLogger(__name__)


class StoreConfigurationReceiverComponent(Component):
    """Receives and parses the feature store configuration over feast-configuration relation."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = "feast-configuration",
    ):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.charm = charm

        self.requirer = FeastStoreConfigurationRequirer(
            charm=self.charm, relation_name=self.relation_name
        )

        self._events_to_observe = [self.requirer.on.updated]

    def get_feature_store_yaml(self) -> Optional[str]:
        """Return the feature_store.yaml config from the relation.

        Raises:
            ErrorWithStatus: wrapping the correct StatusBase depending on the cause.
        """
        relation = self.charm.model.get_relation(self.relation_name)
        if not relation:
            raise ErrorWithStatus(
                f"Missing relation: {self.relation_name}",
                BlockedStatus,
            )

        try:
            yaml_config = self.requirer.get_feature_store_yaml()
            return yaml_config

        except (
            FeastStoreConfigurationRelationError,
            FeastStoreConfigurationRelationDataMissingError,
        ) as e:
            raise ErrorWithStatus(
                f"Waiting for relation data: {e}",
                WaitingStatus,
            )

        except FeastStoreConfigurationDataInvalidError as e:
            raise ErrorWithStatus(
                f"Invalid relation data: {e}",
                BlockedStatus,
            )

    def get_status(self) -> StatusBase:
        """Return status based on whether feature store YAML is present and valid."""
        try:
            receiver = self.charm.store_configuration_receiver.component
            feature_store_yaml = receiver.get_feature_store_yaml()
            if not feature_store_yaml:
                return WaitingStatus("feature_store.yaml is missing or empty")
        except ErrorWithStatus as err:
            return err.status

        return ActiveStatus()
