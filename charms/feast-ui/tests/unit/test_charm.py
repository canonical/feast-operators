from pathlib import Path
from unittest.mock import patch

import ops
import pytest
import yaml
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Container, Context, State

from charm import FeastUICharm

EXPECTED_INGRESS_PATH_MATCHED_PREFIX = "/feast/"
EXPECTED_INGRESS_PATH_REWRITTEN_PREFIX = "/"
EXPECTED_K8S_SERVICE_HTTP_PORT = 8888
RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS = "feast-configuration"
RELATION_ENDPOINT_FOR_INGRESS_IN_AMBIENT_MODE = "istio-ingress-route"
RELATION_ENDPOINT_FOR_INGRESS_IN_SIDECAR_MODE = "ingress"
RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS = "feast_configuration"
RELATION_INTERFACE_FOR_INGRESS_IN_AMBIENT_MODE = "istio_ingress_route"
RELATION_INTERFACE_FOR_INGRESS_IN_SIDECAR_MODE = "ingress"
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
MOCKED_VALID_FEATURE_STORE_CONFIGURATIONS = """project: my_project
registry: data/registry.db
provider: local
online_store:
  type: sqlite
  path: data/online_store.db
entity_key_serialization_version: 2
"""


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
                endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
                interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
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
                endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
                interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
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
                endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
                interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
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
    return_value=MOCKED_VALID_FEATURE_STORE_CONFIGURATIONS,
)
def test_valid_feature_store_yaml(mock_get_yaml, ctx):
    """Test successful YAML config results in ActiveStatus."""
    state_in = State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
                interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
            )
        ],
        containers=[Container(name="feast-ui", can_connect=True)],
    )
    state_out = ctx.run(ctx.on.install(), state_in)

    assert state_out.unit_status == ActiveStatus()


@patch(
    "components.store_configuration_reciver_component.StoreConfigurationReceiverComponent"
    ".get_feature_store_yaml",
    return_value=MOCKED_VALID_FEATURE_STORE_CONFIGURATIONS,
)
@pytest.mark.parametrize("add_ambient_mode_ingress", [True, False], ids=["ambient", "no-ambient"])
@pytest.mark.parametrize("add_sidecar_mode_ingress", [True, False], ids=["sidecar", "no-sidecar"])
def test_istio_relations_conflict_detector(
    mock_get_yaml, ctx, add_ambient_mode_ingress, add_sidecar_mode_ingress,
):
    """Test the status of the conflict detector based on enabled ingress relations."""
    # arrange:
    relations = [
        ops.testing.Relation(
            endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
            interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
        )
    ]
    if add_ambient_mode_ingress:
        relations.append(
            ops.testing.Relation(
                endpoint=RELATION_ENDPOINT_FOR_INGRESS_IN_AMBIENT_MODE,
                interface=RELATION_INTERFACE_FOR_INGRESS_IN_AMBIENT_MODE,
            )
        )
    if add_sidecar_mode_ingress:
        relations.append(
            ops.testing.Relation(
                endpoint=RELATION_ENDPOINT_FOR_INGRESS_IN_SIDECAR_MODE,
                interface=RELATION_INTERFACE_FOR_INGRESS_IN_SIDECAR_MODE,
                remote_app_data={"_supported_versions": "- v1"},
            )
        )
    state_in = State(
        leader=True,
        relations=relations,
        containers=[Container(name="feast-ui", can_connect=True)],
    )

    # act:
    state_out = ctx.run(ctx.on.install(), state_in)

    # assert:
    status = state_out.unit_status
    if add_ambient_mode_ingress and add_sidecar_mode_ingress:
        assert isinstance(status, BlockedStatus)
        assert (
            f"Cannot have both '{RELATION_ENDPOINT_FOR_INGRESS_IN_AMBIENT_MODE}' and "
            f"'{RELATION_ENDPOINT_FOR_INGRESS_IN_SIDECAR_MODE}' relations at the same time."
        ) in status.message
    else:
        assert isinstance(status, ActiveStatus)


@patch(
    "components.store_configuration_reciver_component.StoreConfigurationReceiverComponent"
    ".get_feature_store_yaml",
    return_value=MOCKED_VALID_FEATURE_STORE_CONFIGURATIONS,
)
@pytest.mark.parametrize("config_submission_broken", [True, False], ids=["broken", "good"])
@pytest.mark.parametrize("is_ingress_ready", [True, False], ids=["ready", "not-ready"])
@pytest.mark.parametrize("is_unit_leader", [True, False], ids=["leader", "non-leader"])
def test_ambient_mode_ingress_configurations(
    mock_get_yaml,
    ctx,
    config_submission_broken,
    is_ingress_ready,
    is_unit_leader
):
    """Test that the ingress configurations are correctly submitted based on leadership."""
    # arrange:

    state_in = State(
        leader=is_unit_leader,
        relations=[
            ops.testing.Relation(
                endpoint=RELATION_ENDPOINT_FOR_FEAST_CONFIGURATIONS,
                interface=RELATION_INTERFACE_FOR_FEAST_CONFIGURATIONS,
            ),
            ops.testing.Relation(
                endpoint=RELATION_ENDPOINT_FOR_INGRESS_IN_AMBIENT_MODE,
                interface=RELATION_INTERFACE_FOR_INGRESS_IN_AMBIENT_MODE,
            ),
        ],
        containers=[Container(name="feast-ui", can_connect=True)],
    )
    with ctx(ctx.on.install(), state_in) as manager:  # to access the charm, necessary for mocking
        charm = manager.charm
        # mocking the behavior of the ingress attribute of the charm according to the test case:
        with patch.object(charm, "ambient_mode_ingress") as mocked_ingress:
            mocked_ingress.is_ready.return_value = is_ingress_ready
            if config_submission_broken:
                mocked_ingress.submit_config.side_effect = Exception("Test case's exception!")

            # act:

            state_out = manager.run()

            # assert:

            ingress_submit_config = mocked_ingress.submit_config

            if is_unit_leader and is_ingress_ready:
                ingress_submit_config.assert_called_once()

                # asserting one and only one HTTPRoute is defined:
                submitted_ingress_configurations = ingress_submit_config.call_args.args[0]
                assert len(submitted_ingress_configurations.http_routes) == 1
                first_and_only_httproute = submitted_ingress_configurations.http_routes[0]

                # asserting that the first and only HTTPRoute defined holds the expected...

                # ...matches:
                assert len(first_and_only_httproute.matches) == 1
                assert (
                    first_and_only_httproute.matches[0].path.value
                    == EXPECTED_INGRESS_PATH_MATCHED_PREFIX
                )

                # ...filters:
                assert len(first_and_only_httproute.filters) == 1
                assert (
                    first_and_only_httproute.filters[0].urlRewrite.path.value
                    == EXPECTED_INGRESS_PATH_REWRITTEN_PREFIX
                )

                # ...backends:
                assert len(first_and_only_httproute.backends) == 1
                assert first_and_only_httproute.backends[0].service == METADATA["name"]
                assert first_and_only_httproute.backends[0].port == EXPECTED_K8S_SERVICE_HTTP_PORT

                # asserting broken configuration submissions do not compromise the unit status:
                if config_submission_broken:
                    assert isinstance(state_out.unit_status, ActiveStatus)

            else:
                ingress_submit_config.assert_not_called()
