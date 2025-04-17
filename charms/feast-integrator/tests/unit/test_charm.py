from unittest.mock import patch

import ops
import ops.testing as testing
import pytest
from ops.testing import Context, State

from charm import FeastIntegratorCharm


@pytest.fixture
def ctx():
    return Context(FeastIntegratorCharm)


@pytest.mark.parametrize(
    "leader, expected_status",
    [
        (
            False,
            ops.WaitingStatus("[leadership-gate] Waiting for leadership"),
        ),
        (
            True,
            ops.BlockedStatus("[offline-store] Please add the missing relation: offline-store"),
        ),
    ],
)
def test_install_leadership_status(ctx, leader, expected_status):
    """Test install status depending on leadership state."""
    # GIVEN the unit is (or is not) leader
    state_in = State(leader=leader)

    # WHEN install fires
    state_out = ctx.run(ctx.on.install(), state_in)

    # THEN the unit status is set accordingly
    assert state_out.unit_status == expected_status


@pytest.mark.parametrize(
    "relations, expected_status",
    [
        (
            [testing.Relation(endpoint="offline-store", interface="postgresql_client")],
            ops.BlockedStatus("[online-store] Please add the missing relation: online-store"),
        ),
        (
            [
                testing.Relation(endpoint="offline-store", interface="postgresql_client"),
                testing.Relation(endpoint="online-store", interface="postgresql_client"),
            ],
            ops.BlockedStatus("[registry] Please add the missing relation: registry"),
        ),
    ],
)
def test_install_partial_database_relations(ctx, relations, expected_status):
    """Test unit status when various combinations of database relations are added."""
    # GIVEN the unit is leader and has the parametrized relations
    state_in = State(leader=True, relations=relations)

    # WHEN install fires
    state_out = ctx.run(ctx.on.install(), state_in)

    # THEN the unit status is set to the expected parametrized status
    assert state_out.unit_status == expected_status


def test_install_all_relations_added_database_relation_empty(ctx):
    """Test unit status when all expected relations are added but database relations are empty."""
    # GIVEN the unit is leader and all the expected relations are added but with empty databag
    relations = [
        testing.Relation(
            endpoint="offline-store", interface="postgresql_client", remote_app_data={}
        ),
        testing.Relation(endpoint="online-store", interface="postgresql_client"),
        testing.Relation(endpoint="registry", interface="postgresql_client"),
        testing.Relation(endpoint="secrets", interface="kubernetes_manifest"),
        testing.Relation(endpoint="pod-defaults", interface="kubernetes_manifest"),
    ]

    state_in = State(leader=True, relations=relations)

    # WHEN install fires
    state_out = ctx.run(ctx.on.install(), state_in)

    # THEN the unit status is set to the WaitingStatus
    assert state_out.unit_status == ops.WaitingStatus(
        "[offline-store] Waiting for offline-store relation data"
    )


@patch("components.database_requirer_component.PostgresRequirerComponent.fetch_relation_data")
def test_install_database_relations_added(mock_fetch_relation_data, ctx):
    """Test unit status when all database relations are added with the expected data."""
    # GIVEN that
    # * the unit is leader
    # * database and kubernetes_manifest relations are added
    # * fetch_relation_data returns the db configuration as expected

    mock_data = {
        "host": "localhost",
        "port": 5432,
        "database": "mydb",
        "user": "myuser",
        "password": "mypassword",
    }

    mock_fetch_relation_data.return_value = mock_data

    relations = [
        testing.Relation(
            endpoint="offline-store", interface="postgresql_client", remote_app_data={}
        ),
        testing.Relation(endpoint="online-store", interface="postgresql_client"),
        testing.Relation(endpoint="registry", interface="postgresql_client"),
        testing.Relation(endpoint="secrets", interface="kubernetes_manifest"),
        testing.Relation(endpoint="pod-defaults", interface="kubernetes_manifest"),
    ]

    state_in = State(leader=True, relations=relations)

    # WHEN install fires
    state_out = ctx.run(ctx.on.install(), state_in)

    # THEN the unit status is set to ActiveStatus
    assert state_out.unit_status == ops.ActiveStatus()
