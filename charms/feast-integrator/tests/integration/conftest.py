# tests/integration/conftest.py

import jubilant
import pytest


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    keep_models = bool(request.config.getoption("--keep-models"))
    model = request.config.getoption("--model")

    if model:
        juju = jubilant.Juju(model=model)
        juju.wait_timeout = 10 * 60

        yield juju  # run the test

        if request.session.testsfailed:
            log = juju.debug_log(limit=1000)
            print(log, end="")

    else:
        with jubilant.temp_model(keep=keep_models) as juju:
            juju.wait_timeout = 10 * 60

            yield juju  # run the test

            if request.session.testsfailed:
                log = juju.debug_log(limit=1000)
                print(log, end="")


def pytest_addoption(parser):
    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="keep temporarily-created models",
    )
    parser.addoption(
        "--model",
        action="store",
        help="Juju model to use; if not provided, a new model "
        "will be created for each test which requires one",
        default=None,
    )
    parser.addoption(
        "--charm-path",
        help="Path to charm file for performing tests on.",
    )
