import logging
from typing import Dict

from charmed_kubeflow_chisme.components.component import Component
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires, DataInterfacesError
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus

logger = logging.getLogger(__name__)


class PostgresRequirerComponent(Component):
    """
    A Reusable component responsible for handling the relation with PostgreSQL charm.

    Args:
        charm(CharmBase): the requirer charm
        relation_name(str): name of the relation that uses the postgresql_client interface
        database_name(str): name of the database requested by the requirer
    """

    def __init__(self, charm: CharmBase, relation_name: str, database_name: str):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.charm = charm
        self.database_name = database_name

        self.database = DatabaseRequires(
            charm=charm, relation_name=relation_name, database_name=database_name
        )

        self._events_to_observe = [
            self.database.on.database_created,
            self.database.on.endpoints_changed,
        ]

    def fetch_relation_data(self) -> Dict[str, str]:
        """Fetch postgres relation data.

        Retrieves relation data from a database using the `fetch_relation_data` method of
        the `database` object. The retrieved data is then logged for debugging purposes,
        and any non-empty data is processed to extract endpoint information, username,
        and password. This processed data is then returned as a dictionary.
        If no data is retrieved, the unit is set to waiting status and the program
        exits with a zero status code.
        """
        relations = self.database.fetch_relation_data()
        logger.debug("Got following database data: %s", relations)
        for data in relations.values():
            if not data:
                continue
            logger.info("New PSQL database endpoint is %s", data["endpoints"])
            prefix = self.database_name
            host, port = data["endpoints"].split(":")

            fields = {
                "host": host,
                "port": port,
                "database": data["database"],
                "user": data["username"],
                "password": data["password"],
            }
            # Add the database name as a prefix to the dict key to distinguish different DBs
            db_data = {f"{prefix}_{key}": value for key, value in fields.items()}
            return db_data
        return {}

    def get_status(self) -> StatusBase:
        """Return this component's status based on the presence of the relation and its data."""
        if not self.charm.model.get_relation(self.relation_name):
            # We need the user to do 'juju integrate'.
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")

        try:
            self.fetch_relation_data()
        except (DataInterfacesError, KeyError):
            # We need the charms to finish integrating.
            return WaitingStatus(f"Waiting for {self.relation_name} relation data")
        else:
            logger.info(f"Database {self.relation_name} data: {self.fetch_relation_data()}")
            return ActiveStatus()
