from pathlib import Path
from unittest.mock import patch

import ops
import pytest
import yaml
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Container, Context, State

from charm import FeastUICharm

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@pytest.fixture()
def ctx() -> Context:
    ctx = Context(FeastUICharm, meta=METADATA, config={}, actions={}, unit_id=0)
    return ctx


@pytest.mark.parametrize(
    "leader, expected_status",
    [
        (False, WaitingStatus("[leadership-gate] Waiting for leadership")),
        (True, BlockedStatus("[feast-configuration] Missing relation: feast-configuration")),
    ],
)
def test_leadership_and_relation_gate(ctx, leader, expected_status):
    state_in = State(leader=leader)
    state_out = ctx.run(ctx.on.install(), state_in)

    assert isinstance(state_out.unit_status, type(expected_status))
    assert expected_status.message in state_out.unit_status.message


def test_relation_exists_but_empty(ctx):
    """Test when relation exists but no data has been exchanged yet."""
    state_in = State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="feast-configuration",
                interface="feast_configuration",
            )
        ],
    )
    state_out = ctx.run(ctx.on.install(), state_in)
    assert "Waiting for relation data" in state_out.unit_status.message


@patch(
    "components.store_configuration_reciver_component.StoreConfigurationReceiverComponent"
    ".get_feature_store_yaml",
    side_effect=ErrorWithStatus("[feast-configuration] Invalid relation data", BlockedStatus),
)
def test_invalid_feature_store_data(mock_get_yaml, ctx):
    """Test charm enters BlockedStatus if config is invalid."""
    state_in = State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="feast-configuration",
                interface="feast_configuration",
            )
        ],
    )
    state_out = ctx.run(ctx.on.install(), state_in)

    assert state_out.unit_status.name == "blocked"
    assert "Invalid relation data" in state_out.unit_status.message


@patch(
    "components.store_configuration_reciver_component.StoreConfigurationReceiverComponent"
    ".get_feature_store_yaml",
    return_value="",
)
def test_empty_feature_store_yaml(mock_get_yaml, ctx):
    """Test charm enters WaitingStatus if feature_store.yaml is empty."""
    state_in = State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="feast-configuration",
                interface="feast_configuration",
            )
        ],
        containers=[Container(name="feast-ui", can_connect=True)],
    )
    state_out = ctx.run(ctx.on.install(), state_in)

    assert isinstance(state_out.unit_status, WaitingStatus)
    assert "feature_store.yaml is missing or empty" in state_out.unit_status.message


@patch(
    "components.store_configuration_reciver_component.StoreConfigurationReceiverComponent"
    ".get_feature_store_yaml",
    return_value="""project: my_project
registry: data/registry.db
provider: local
online_store:
  type: sqlite
  path: data/online_store.db
entity_key_serialization_version: 2
""",
)
def test_valid_feature_store_yaml(mock_get_yaml, ctx):
    """Test successful YAML config results in ActiveStatus."""
    state_in = State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="feast-configuration",
                interface="feast_configuration",
            )
        ],
        containers=[Container(name="feast-ui", can_connect=True)],
    )
    state_out = ctx.run(ctx.on.install(), state_in)

    assert state_out.unit_status == ActiveStatus()
