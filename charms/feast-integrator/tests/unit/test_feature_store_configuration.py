import pytest
import ops
from ops import testing
from lib.charms.feast_integrator.v0.feast_store_configuration import FeastStoreConfigurationProvider, FeastStoreConfigurationRequirer

TEST_RELATION_NAME = "test-relation"


@pytest.fixture
def provider_charm_type():
    class TestProviderCharm(ops.CharmBase):
        META = {
            "name": "provider-test-charm",
            "provides":
                {TEST_RELATION_NAME: {"interface": "test-interface"}}
        }

        def __init__(self, framework: ops.Framework):
            super().__init__(framework)
            self.feast_configuration_provider = FeastStoreConfigurationProvider(self, relation_name=TEST_RELATION_NAME)

    return TestProviderCharm

@pytest.fixture
def provider_context(provider_charm_type):
    return testing.Context(provider_charm_type, meta=provider_charm_type.META)

@pytest.fixture
def requirer_charm_type():
    class TestRequirerCharm(ops.CharmBase):
        META = {
            "name": "requirer-test-charm",
            "requires":
                {TEST_RELATION_NAME: {"interface": "test-interface"}}
        }

        def __init__(self, framework: ops.Framework):
            super().__init__(framework)
            self.feast_configuration_requirer= FeastStoreConfigurationRequirer(self, relation_name=TEST_RELATION_NAME)

    return TestRequirerCharm

@pytest.fixture
def requirer_context(requirer_charm_type):
    return testing.Context(requirer_charm_type, meta=requirer_charm_type.META)   

@pytest.mark.parametrize('event_name, expected_event', (
    ('start', ops.charm.StartEvent),
    ('install', ops.charm.InstallEvent),
    ('stop', ops.charm.StopEvent),
    ('remove', ops.charm.RemoveEvent),
    ('update_status', ops.charm.UpdateStatusEvent),
))
def test_provider_charm_runs(provider_context, event_name, expected_event):
    """Verify that the provider charm can create the library object, and handles each lifecycle event correctly."""
    ctx = provider_context
    state_in = testing.State()
    ctx.run(getattr(ctx.on, event_name)(), state_in)
    assert len(ctx.emitted_events) == 1
    assert isinstance(ctx.emitted_events[0], expected_event)