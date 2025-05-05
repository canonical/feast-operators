"""Chisme component to manage the provider of feast-configuration relation."""

import dataclasses
import logging

from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charms.feast_integrator.v0.feast_store_configuration import (
    FeastStoreConfiguration,
    FeastStoreConfigurationDataInvalidError,
    FeastStoreConfigurationProvider,
    FeastStoreConfigurationRelationError,
)
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class StoreConfigurationSenderInputs:
    """Defines the required inputs for StoreConfigurationSenderComponent."""

    context: dict


class StoreConfigurationSenderComponent(Component):
    """Sends the Feature Store Configuration via the feast_configuration interface.

    A Component that creates a FeastStoreConfiguration object and sends it using the
    feast_store_configuration_library over the feast_configuration interface.

    Args:
        charm(CharmBase): the requirer charm
        relation_name(str, Optional): name of the relation that uses
        the feast_configuration interface
    """

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = "feast-configuration",
        *args,
        **kwargs,
    ):
        super().__init__(charm, relation_name, *args, **kwargs)
        self.charm = charm
        self.relation_name = relation_name

        self.store_configuration_provider = FeastStoreConfigurationProvider(
            charm=self.charm, relation_name=self.relation_name
        )

    def create_store_configuration(self) -> FeastStoreConfiguration:
        """Create the FeastStoreConfiguration from the input context."""
        # Get databases context
        context = self._inputs_getter().context

        # Create FeastStoreConfiguration
        try:
            store_configuration = FeastStoreConfiguration(**context)
        # Catch errors due to validation failure on configuration data types
        except FeastStoreConfigurationDataInvalidError as e:
            raise ErrorWithStatus(e.message, BlockedStatus)
        # Catch errors due to missing or unexpected fields
        except TypeError as e:
            error_msg = str(e)

            if "missing" in error_msg and "required positional argument" in error_msg:
                raise ErrorWithStatus(
                    f"Missing required fields in creating FeastStoreConfiguration: {error_msg}",
                    BlockedStatus,
                ) from e

            elif "unexpected keyword argument" in error_msg:
                raise ErrorWithStatus(
                    f"Unexpected field(s) in relation data: {error_msg}", BlockedStatus
                ) from e

            else:
                raise ErrorWithStatus(
                    f"Unexpected data provided to FeastStoreConfiguration: {error_msg}",
                    BlockedStatus,
                ) from e

        return store_configuration

    def send_store_configuration(self) -> None:
        """Create the FeastStoreConfiguration and send it over the relation."""
        # Get store configuration object
        store_configuration = self.create_store_configuration()

        # Send store configuration using library API
        self.store_configuration_provider.send_data(store_configuration)

    def get_status(self) -> StatusBase:
        """Return this component's status based on the relation."""
        # Check that configuration context is available in the input
        try:
            self._inputs_getter()
        except Exception as err:
            return WaitingStatus(f"Store configuration not provided: {err}")

        if not self.charm.model.get_relation(self.relation_name):
            logger.warning(f"Relation {self.relation_name} not added, UI is not integrated.")
            return ActiveStatus()

        # Try to send the store configuration
        try:
            self.send_store_configuration()
        except FeastStoreConfigurationRelationError as err:
            return WaitingStatus(f"Relation {self.relation_name} error: {err}")
        except ErrorWithStatus as err:
            return err.status
        return ActiveStatus()
