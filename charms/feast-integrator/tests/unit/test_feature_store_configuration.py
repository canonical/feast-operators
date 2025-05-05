import ops
import pytest
from ops.testing import Context, Relation, State
from scenario import JujuLogLine

from lib.charms.feast_integrator.v0.feast_store_configuration import (
    FeastStoreConfiguration,
    FeastStoreConfigurationProvider,
    FeastStoreConfigurationRequirer,
)

TEST_RELATION_NAME = "test-relation"
TEST_INTERFACE_NAME = "test-interface"

MOCK_CONFIG_DICT = {
    "registry_user": "test_registry_user",
    "registry_password": "securepassword",
    "registry_host": "registry.example.com",
    "registry_port": "5432",
    "registry_database": "registry_db",
    "offline_store_host": "offline-db.example.com",
    "offline_store_port": "3306",
    "offline_store_database": "offline_db",
    "offline_store_user": "offline_user",
    "offline_store_password": "offline_pass",
    "online_store_host": "online-db.example.com",
    "online_store_port": "6379",
    "online_store_database": "online_db",
    "online_store_user": "online_user",
    "online_store_password": "online_pass",
}


@pytest.fixture
def provider_charm_type():
    class TestProviderCharm(ops.CharmBase):
        META = {
            "name": "provider-test-charm",
            "provides": {TEST_RELATION_NAME: {"interface": TEST_INTERFACE_NAME}},
        }

        def __init__(self, framework: ops.Framework):
            super().__init__(framework)
            self.feast_configuration_provider = FeastStoreConfigurationProvider(
                self, relation_name=TEST_RELATION_NAME
            )

    return TestProviderCharm


@pytest.fixture
def provider_context(provider_charm_type):
    return Context(provider_charm_type, meta=provider_charm_type.META)


@pytest.fixture
def requirer_charm_type():
    class TestRequirerCharm(ops.CharmBase):
        META = {
            "name": "requirer-test-charm",
            "requires": {TEST_RELATION_NAME: {"interface": TEST_INTERFACE_NAME}},
        }

        def __init__(self, framework: ops.Framework):
            super().__init__(framework)
            self.feast_configuration_requirer = FeastStoreConfigurationRequirer(
                self, relation_name=TEST_RELATION_NAME
            )

    return TestRequirerCharm


@pytest.fixture
def requirer_context(requirer_charm_type):
    return Context(requirer_charm_type, meta=requirer_charm_type.META)


@pytest.mark.parametrize(
    "event_name, expected_event",
    (
        ("start", ops.charm.StartEvent),
        ("install", ops.charm.InstallEvent),
        ("stop", ops.charm.StopEvent),
        ("remove", ops.charm.RemoveEvent),
        ("update_status", ops.charm.UpdateStatusEvent),
    ),
)
def test_provider_charm_runs(provider_context, event_name, expected_event):
    """Test that a provider charm can initialise the library, and no unexpected events emitted."""
    ctx = provider_context
    state_in = State(leader=True)
    ctx.run(getattr(ctx.on, event_name)(), state_in)
    assert len(ctx.emitted_events) == 1
    assert isinstance(ctx.emitted_events[0], expected_event)


@pytest.mark.parametrize(
    "event_name, expected_event",
    (
        ("start", ops.charm.StartEvent),
        ("install", ops.charm.InstallEvent),
        ("stop", ops.charm.StopEvent),
        ("remove", ops.charm.RemoveEvent),
        ("update_status", ops.charm.UpdateStatusEvent),
    ),
)
def test_requirer_charm_runs(requirer_context, event_name, expected_event):
    """Test that a requirer charm can initialise the library, and no unexpected events emitted."""
    ctx = requirer_context
    state_in = State()
    ctx.run(getattr(ctx.on, event_name)(), state_in)
    assert len(ctx.emitted_events) == 1
    assert isinstance(ctx.emitted_events[0], expected_event)


def test_requirer_get_feature_store_yaml(requirer_context):
    """Assert the relation data is retrieved using the library as expected."""
    # Create mock relation data
    expected_data_yaml = f"""project: feast_project
registry:
  registry_type: sql
  path: postgresql://{MOCK_CONFIG_DICT["registry_user"]}:{MOCK_CONFIG_DICT["registry_password"]}@{MOCK_CONFIG_DICT["registry_host"]}:{int(MOCK_CONFIG_DICT["registry_port"])}/{MOCK_CONFIG_DICT["registry_database"]}
  cache_ttl_seconds: 60
  sqlalchemy_config_kwargs:
    echo: false
    pool_pre_ping: true
provider: local
offline_store:
  type: postgres
  host: {MOCK_CONFIG_DICT["offline_store_host"]}
  port: {int(MOCK_CONFIG_DICT["offline_store_port"])}
  database: {MOCK_CONFIG_DICT["offline_store_database"]}
  db_schema: public
  user: {MOCK_CONFIG_DICT["offline_store_user"]}
  password: {MOCK_CONFIG_DICT["offline_store_password"]}
online_store:
  type: postgres
  host: {MOCK_CONFIG_DICT["online_store_host"]}
  port: {int(MOCK_CONFIG_DICT["online_store_port"])}
  database: {MOCK_CONFIG_DICT["online_store_database"]}
  db_schema: public
  user: {MOCK_CONFIG_DICT["online_store_user"]}
  password: {MOCK_CONFIG_DICT["online_store_password"]}
entity_key_serialization_version: 2
"""

    # GIVEN the requirer charm has a relation with the feast config in the data bag
    relation = Relation(endpoint=TEST_RELATION_NAME, remote_app_data=MOCK_CONFIG_DICT)
    state_in = State(relations={relation})

    # WHEN start fires
    with requirer_context(requirer_context.on.start(), state=state_in) as manager:
        feature_store_yaml = manager.charm.feast_configuration_requirer.get_feature_store_yaml()

    # THEN the feature store yaml is as expected
    assert feature_store_yaml == expected_data_yaml


def test_provider_send_data(provider_context):
    """Assert that the relation data is sent by the provider charm as expected."""
    mock_config = FeastStoreConfiguration(**MOCK_CONFIG_DICT)

    # GIVEN the provider charm has a relation with the test relation name
    relation = Relation(endpoint=TEST_RELATION_NAME, interface=TEST_INTERFACE_NAME)
    state_in = State(leader=True, relations={relation})

    with provider_context(provider_context.on.start(), state=state_in) as manager:
        # GIVEN send_data is called
        state_out = manager.run()
        manager.charm.feast_configuration_provider.send_data(mock_config)

    # THEN the relation data contains the store configuration dict as expected
    relation_data = state_out.get_relation(relation.id).local_app_data
    assert relation_data == MOCK_CONFIG_DICT


def test_provider_send_data_not_leader(provider_context):
    """Assert that the relation data is not sent by the provider when not leader unit."""
    mock_config = FeastStoreConfiguration(**MOCK_CONFIG_DICT)

    # GIVEN the provider charm has a relation with the test relation name
    relation = Relation(endpoint=TEST_RELATION_NAME, interface=TEST_INTERFACE_NAME)
    state_in = State(leader=False, relations={relation})

    with provider_context(provider_context.on.start(), state=state_in) as manager:
        # GIVEN send_data is called
        state_out = manager.run()
        manager.charm.feast_configuration_provider.send_data(mock_config)

        # THEN the expected log is sent to juju
        expected_log = JujuLogLine(
            level="INFO",
            message=(
                "StoreConfigurationProivder handled send_data event when it is not the leader."
                "Skipping event - no data sent."
            ),
        )

        assert expected_log in provider_context.juju_log

    # THEN the relation data is empty
    relation_data = state_out.get_relation(relation.id).local_app_data
    assert relation_data == {}

def test_feast_store_configuration_type_validation_failure():
    """Test that FeastStoreConfiguration raises TypeError when a field has incorrect type."""

    # Inject a wrong type (e.g., string instead of int)
    invalid_data = MOCK_CONFIG_DICT.copy()
    invalid_data["registry_port"] = "not-a-port"

    with pytest.raises(TypeError) as exc_info:
        FeastStoreConfiguration(**invalid_data)

    assert "registry_port must be an int or a string representing an int" in str(exc_info.value)
