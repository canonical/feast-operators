# Copyright 2025 Canonical Ltd.

"""Defines Chisme components for the charm."""

import logging

from charmed_kubeflow_chisme.components.pebble_component import PebbleServiceComponent
from ops.pebble import Layer

logger = logging.getLogger(__name__)


class FeastUIPebbleService(PebbleServiceComponent):
    """Pebble service component for Feast UI."""

    def __init__(self, app_port: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_port = app_port

    def get_layer(self) -> Layer:
        """Return Pebble layer configuration for the service.

        This method is required for subclassing PebbleServiceContainer.
        """
        logger.info("PebbleServiceComponent.get_layer executing")
        return Layer(
            {
                "summary": "feast-ui layer",
                "description": "Pebble config layer for feast-ui",
                "services": {
                    self.service_name: {
                        "override": "replace",
                        "summary": "Entry point for feast-ui image",
                        "command": (
                            f"feast ui --host 0.0.0.0 --port {self.app_port} --root_path /feast"
                        ),
                        "startup": "enabled",
                        "working-dir": "/home/ubuntu",
                    }
                },
            }
        )
