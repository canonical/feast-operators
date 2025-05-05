"""Library for sharing Feast store configuration information.

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

### Add relation to metadata.yaml
```yaml
requires:
  feast-configuration:
    interface: feast-configuration
    limit: 1
```

### Instantiate the  class in charm.py

```python
from ops.charm import CharmBase
from charms.feast_integrator.v0.feast_store_configuration import (
    FeastStoreConfigurationRequirer,
    FeastStoreConfigurationRelationError
)

class RequirerCharm(CharmBase):
    def __init__(self, *args):
        self.feast_configuration_requirer = FeastStoreConfigurationRequirer(self)
        self.framework.observe(self.on.some_event_emitted, self.some_event_function)

    def some_event_function():
        # use the getter function wherever the info is needed
        try:
            feast_configuration_yaml = self.feast_configuration_requirer.get_feature_store_yaml()
        except FeastStoreConfigurationRelationError as error:
            "your error handler goes here"
```

## Using the library as provider

### Add relation to metadata.yaml

```yaml
provides:
  feast-configuration:
    interface: feast-configuration
    limit: 1
```

### Instantiate the  class in charm.py

```python
from ops.charm import CharmBase
from charms.feast_integrator.v0.feast_store_configuration import (
FeastStoreConfigurationProvider,
FeastStoreConfigurationRelationMissingError
)

class ProviderCharm(CharmBase):
    def __init__(self, *args, **kwargs):
        ...
        self.feast_configuration_provider = FeastStoreConfigurationProvider(self)
        self.observe(self.on.some_event, self._some_event_handler)

    def _some_event_handler(self, ...):
        # Create the FeastStoreConfiguration object
        store_config = FeastStoreConfiguration(
            registry_user="my_user",
            registry_password="pass",
            registry_host="host",
            registry_port=5432,
            registry_database="reg_db",
            offline_store_host="offline_host",
            offline_store_port=3306,
            offline_store_database="offline_db",
            offline_store_user="off_user",
            offline_store_password="off_pass",
            online_store_host="online_host",
            online_store_port=6379,
            online_store_database="online_db",
            online_store_user="on_user",
            online_store_password="on_pass"
        )

        try:
            self.feast_configuration_provider.send_data(store_config)
        except FeastStoreConfigurationRelationMissingError as error:
            "your error handler goes here"
```

## Relation data

The data shared by this library is defined by the FeastStoreConfiguration dataclass.
The attributes of this dataclass are shared in the relation data bag as a dictionary.
"""

# The unique Charmhub library identifier, never change it
import logging
from dataclasses import asdict, dataclass
from typing import Dict, Optional

import yaml
from ops import BoundEvent, CharmBase, EventSource, Object, ObjectEvents, RelationEvent

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


class FeastStoreConfigurationEvents(ObjectEvents):
    """Events for the Feast Store Configuration library."""

    updated = EventSource(FeastStoreConfigurationUpdatedEvent)


class FeastStoreConfigurationRelationError(Exception):
    """Base exception class for any relation error handled by this library."""

    pass


class FeastStoreConfigurationRelationMissingError(FeastStoreConfigurationRelationError):
    """Exception to raise when the relation is missing on either end."""

    def __init__(self, relation_name):
        self.message = f"Missing relation with name {relation_name} with a store configuration provider."
        super().__init__(self.message)


class FeastStoreConfigurationRelationDataMissingError(FeastStoreConfigurationRelationError):
    """Exception to raise when there is missing data in the relation data bag."""

    def __init__(self, relation_name):
        self.message = f"No data found in relation {relation_name} data bag."
        super().__init__(self.message)

class FeastStoreConfigurationDataInvalidError(Exception):
    """Exception to raise when the data in the relation data bag has incorrect format."""

    def __init__(self, error):
        self.message = f"Data format for FeastStoreConfiguration has incorrect format: {error}."
        super().__init__(self.message)

@dataclass
class FeastStoreConfiguration:
    """Configuration parameters for generating a Feast feature store.

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

    def __post_init__(self):
        for field_name, expected_type in self.__annotations__.items():
            value = getattr(self, field_name)

            # Convert str to int where expected
            if expected_type is int:
                if isinstance(value, str):
                    try:
                        value = int(value)
                        setattr(self, field_name, value)
                    except ValueError:
                        raise FeastStoreConfigurationDataInvalidError(
                            f"{field_name} must be int or string representing an int, got :{value}"
                        )

            # Final strict type check after any conversion
            if not isinstance(value, expected_type):
                raise FeastStoreConfigurationDataInvalidError(
                    f"{field_name} must be of type {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )


class FeastStoreConfigurationProvider(Object):
    """Implement the Provider end of the Feast Configuration relation.

    Attributes:
        charm (CharmBase): the requirer application
        relation_name (str, optional): the name of the relation
    """

    on = FeastStoreConfigurationEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_name: Optional[str] = DEFAULT_RELATION_NAME,
    ):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name

    def send_data(self, store_configuration: FeastStoreConfiguration):
        """Update the relation data bag with data from a Store Configuration.

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

        relation = self.model.get_relation(self.relation_name)

        if not relation:
            raise FeastStoreConfigurationRelationMissingError(self.relation_name)

        relation_data = {k: str(v) for k, v in asdict(store_configuration).items()}

        # Update relation data
        logger.debug(f"Sending data {relation_data}")
        relation.data[self.charm.app].update(relation_data)


class FeastStoreConfigurationRequirer(Object):
    """Implement the Requirer end of the Feast Configuration relation.

    Attributes:
        charm (CharmBase): the requirer application
        relation_name (str, optional): the name of the relation
    """

    on = FeastStoreConfigurationEvents()

    def __init__(self, charm: CharmBase, relation_name: Optional[str] = DEFAULT_RELATION_NAME):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name

        self.framework.observe(
            self.charm.on[self.relation_name].relation_changed, self._on_relation_changed
        )

        self.framework.observe(
            self.charm.on[self.relation_name].relation_broken, self._on_relation_broken
        )

    def _on_relation_changed(self, event: BoundEvent) -> None:
        """Handle relation-changed event for this relation."""
        self.on.updated.emit(event.relation)

    def _on_relation_broken(self, event: BoundEvent) -> None:
        """Handle relation-broken event for this relation."""
        self.on.updated.emit(event.relation)

    def get_feature_store_yaml(self):
        """Generate the Feast feature_store.yaml content from a FeastConfiguration instance.

        Args:
            config (FeastConfiguration): The configuration values to populate the YAML.

        Returns:
            str: A string representation of the feature_store.yaml file.

        Raises:
            FeatureStoreConfigurationRelationDataMissingError if data is missing
            FeatureStoreConfigurationRelationMissingError: if there is no related application
        """
        relation = self.model.get_relation(self.relation_name)

        if not relation:
            raise FeastStoreConfigurationRelationMissingError(self.relation_name)

        relation_data = relation.data[relation.app]

        if not relation_data:
            raise FeastStoreConfigurationRelationDataMissingError(self.relation_name)

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
                },
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
