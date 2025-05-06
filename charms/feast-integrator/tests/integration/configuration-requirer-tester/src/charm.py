#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.

"""Mock relation requirer charm."""

import logging

import ops
from charms.feast_integrator.v0.feast_store_configuration import (
    FeastStoreConfigurationRelationError,
    FeastStoreConfigurationRequirer,
)

logger = logging.getLogger(__name__)


class ConfigurationRequirerTesterCharm(ops.CharmBase):
    """Charm for testing requirer of feast-configuration relation."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.feast_configuration_requirer = FeastStoreConfigurationRequirer(self)

        for event in [
            self.on.leader_elected,
            self.on.config_changed,
            self.on.start,
            self.on.install,
            self.on.update_status,
        ]:
            self.framework.observe(event, self._on_event)

        for rel in self.model.relations.keys():
            self.framework.observe(self.on[rel].relation_changed, self._on_event)

    def _on_event(self, _):
        try:
            feast_configuration_yaml = self.feast_configuration_requirer.get_feature_store_yaml()
        except FeastStoreConfigurationRelationError as error:
            self.model.unit.status = ops.BlockedStatus(f"Error with relation: {error}")
            return
        logger.info(f"feast configuration yaml:\n{feast_configuration_yaml}")
        self.model.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(ConfigurationRequirerTesterCharm)
