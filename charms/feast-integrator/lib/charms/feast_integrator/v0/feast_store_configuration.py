"""
Library for sharing Feast store configuration information.

This library offers a Python API for providing and requesting information about
Feast feature store configuration.
The default relation name is `feast-configuration` and it's recommended to use that name,
though if changed, you must ensure to pass the correct name when instantiating the
provider and requirer classes, as well as in `metadata.yaml`.

## Getting Started

### Fetching the library with charmcraft

Using charmcraft you can:
```shell
charmcraft fetch-lib charms.feast_integrator.v0.feast_store_configuration
```

## Using the library as requirer

## Using the library as provider

## Relation data

The data shared by this library is defined by the FeastStoreConfiguration dataclass.
The attributes of this dataclass are shared in the relation data bag as a dictionary.
"""

# The unique Charmhub library identifier, never change it
from dataclasses import asdict, dataclass
import logging
from typing import Dict, Optional
from ops import EventSource, ObjectEvents, RelationEvent, CharmBase
import yaml

logger = logging.getLogger(__name__)

LIBID = "811da8ece74c4c09b53e114cb74d591e"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

DEFAULT_RELATION_NAME = "feast-configuration"

class FeastStoreConfigurationUpdatedEvent(RelationEvent):
    """Indicates the Feast Store Configuration data was updated."""


class FeastStoreConfigurationInfoEvents(ObjectEvents):
    """Events for the Feast Store Configuration library."""

    updated = EventSource(FeastStoreConfigurationUpdatedEvent)

class FeastStoreConfigurationRelationError(Exception):
    """Base exception class for any relation error handled by this library."""

    pass


class FeastStoreConfigurationRelationMissingError(FeastStoreConfigurationRelationError):
    """Exception to raise when the relation is missing on either end."""

    def __init__(self):
        self.message = "Missing relation with a store configuration provider."
        super().__init__(self.message)


class FeastStoreConfigurationRelationDataMissingError(FeastStoreConfigurationRelationError):
    """Exception to raise when there is missing data in the relation data bag."""

    def __init__(self, relation_name):
        self.message = f"No data found in relation {relation_name} data bag."
        super().__init__(self.message)

@dataclass
class FeastStoreConfiguration:
    """
    Configuration parameters for generating a Feast feature store.

    This dataclass captures all dynamic, parameterizable values used in the
    Feast store configuration template. These values are typically substituted into 
    the YAML template at runtime or during deployment to configure connections 
    to the registry, online store, and offline store.

    Attributes:
        registry_user (str): Username for connecting to the registry database.
        registry_password (str): Password for the registry user.
        registry_host (str): Hostname or IP address of the registry database.
        registry_port (int): Port number for the registry database.
        registry_database (str): Name of the registry database.

        offline_store_host (str): Hostname or IP for the offline store database.
        offline_store_port (int): Port number for the offline store.
        offline_store_database (str): Database name for the offline store.
        offline_store_user (str): Username for the offline store.
        offline_store_password (str): Password for the offline store user.

        online_store_host (str): Hostname or IP for the online store database.
        online_store_port (int): Port number for the online store.
        online_store_database (str): Database name for the online store.
        online_store_user (str): Username for the online store.
        online_store_password (str): Password for the online store user.
    """
    # Registry configuration
    registry_user: str
    registry_password: str
    registry_host: str
    registry_port: int
    registry_database: str

    # Offline store configuration
    offline_store_host: str
    offline_store_port: int
    offline_store_database: str
    offline_store_user: str
    offline_store_password: str

    # Online store configuration
    online_store_host: str
    online_store_port: int
    online_store_database: str
    online_store_user: str
    online_store_password: str

class FeastStoreConfigurationProvider():
    """
    Implement the Provider end of the Feast Configuration relation.

    Attributes:
        charm (CharmBase): the requirer application
        relation_name (str, optional): the name of the relation
    """

    on = FeastStoreConfigurationInfoEvents()

    def __init__(self,
                 charm: CharmBase,
                 relation_name: Optional[str] = DEFAULT_RELATION_NAME,
                 ):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name

        self.framework.observe(
            self.charm.on[self._relation_name].relation_changed, self._on_relation_changed
        )

        self.framework.observe(
            self.charm.on[self._relation_name].relation_broken, self._on_relation_broken
        )

    def send_data(self,
                  store_configuration: FeastStoreConfiguration):
        """
        Update the relation data bag with data from a Store Configuration.

        Args:
            store_configuration (StoreConfiguration): the Feast store configuration object
        """
        # Validate unit is leader to send data; otherwise return
        if not self.charm.model.unit.is_leader():
            logger.info(
                "StoreConfigurationProivder handled send_data event when it is not the leader."
                "Skipping event - no data sent."
            )
            return

        relations = self.charm.model.relations[self.relation_name]

        # Update relation data
        for relation in relations:
            relation.data[self.charm.app].update(
                asdict(store_configuration)
            )

class FeastStoreConfigurationRequirer():
    """
    Implement the Requirer end of the Feast Configuration relation.

    Attributes:
        charm (CharmBase): the requirer application
        relation_name (str, optional): the name of the relation
    """

    def __init__(self, charm, relation_name: Optional[str] = DEFAULT_RELATION_NAME):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name

    def get_feature_store_yaml(self):
        """
        Generate the Feast feature_store.yaml content from a FeastConfiguration instance.

        Args:
            config (FeastConfiguration): The configuration values to populate the YAML.

        Returns:
            str: A string representation of the feature_store.yaml file.

        Raises:
            StoreConfigurationRelationDataMissingError if data is missing
            StoreConfigurationRelationMissingError: if there is no related application
        """

        relation = self.model.get_relation(self.relation_name)

        if not relation:
            raise FeastStoreConfigurationRelationMissingError()

        relation_data = relation.data[relation.app]

        if not relation_data:
            raise FeastStoreConfigurationRelationDataMissingError()

        config = FeastStoreConfiguration(**relation_data)

        yaml_dict: Dict = {
            "project": "feast_project",
            "registry": {
                "registry_type": "sql",
                "path": (
                    f"postgresql://{config.registry_user}:{config.registry_password}"
                    f"@{config.registry_host}:{config.registry_port}/{config.registry_database}"
                ),
                "cache_ttl_seconds": 60,
                "sqlalchemy_config_kwargs": {
                    "echo": False,
                    "pool_pre_ping": True,
                }
            },
            "provider": "local",
            "offline_store": {
                "type": "postgres",
                "host": config.offline_store_host,
                "port": config.offline_store_port,
                "database": config.offline_store_database,
                "db_schema": "public",
                "user": config.offline_store_user,
                "password": config.offline_store_password,
            },
            "online_store": {
                "type": "postgres",
                "host": config.online_store_host,
                "port": config.online_store_port,
                "database": config.online_store_database,
                "db_schema": "public",
                "user": config.online_store_user,
                "password": config.online_store_password,
            },
            "entity_key_serialization_version": 2,
        }

        return yaml.dump(yaml_dict, sort_keys=False)
