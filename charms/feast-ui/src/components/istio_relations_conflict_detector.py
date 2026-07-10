# Copyright 2026 Canonical Ltd.

"""Component to detect conflicting Istio relations."""

from logging import getLogger

from charmed_kubeflow_chisme.components import Component
from ops import ActiveStatus, BlockedStatus, StatusBase

logger = getLogger(__name__)


class IstioRelationsConflictDetectorComponent(Component):
    """Component to detect conflicting Istio relations."""

    def __init__(
        self,
        *args,
        ambient_relation_name: str,
        sidecar_relation_name: str,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.sidecar_relation_name = sidecar_relation_name
        self.ambient_relation_name = ambient_relation_name

    def get_status(self) -> StatusBase:  # noqa: D102
        """Check that ambient and sidecar relations are not present simultaneously."""
        # NOTE: use `relations` (a list) rather than `get_relation`, which raises
        # TooManyRelatedAppsError when more than one relation is present on an endpoint.
        ambient_relations = self._charm.model.relations[self.ambient_relation_name]
        sidecar_relations = self._charm.model.relations[self.sidecar_relation_name]

        if ambient_relations and sidecar_relations:
            logger.error(
                f"Both '{self.ambient_relation_name}' and '{self.sidecar_relation_name}' "
                "relations are present, remove one to unblock."
            )
            return BlockedStatus(
                f"Cannot have both '{self.ambient_relation_name}' and "
                f"'{self.sidecar_relation_name}' relations at the same time."
            )
        return ActiveStatus()
