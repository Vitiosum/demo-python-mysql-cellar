"""Test fixtures: a real MySQL database and an in-process S3 (moto).

MySQL: TEST_MYSQL_URI, default mysql://root@127.0.0.1:3306/herbarium_test.
The tests that need it are skipped when it is not reachable.
"""

import os

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine, text

TEST_MYSQL_URI = os.environ.get("TEST_MYSQL_URI", "mysql://root@127.0.0.1:3306/herbarium_test")


def mysql_or_skip() -> str:
    uri = "mysql+pymysql://" + TEST_MYSQL_URI.removeprefix("mysql://")
    try:
        engine = create_engine(uri)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS specimens"))
        engine.dispose()
    except Exception as err:
        pytest.skip(f"MySQL test database not reachable ({type(err).__name__}): set TEST_MYSQL_URI")
    return TEST_MYSQL_URI


@pytest.fixture
def client(monkeypatch):
    from herbarium import main

    monkeypatch.setenv("MYSQL_ADDON_URI", mysql_or_skip())
    # moto intercepts calls to AWS endpoints, so the test "Cellar" lives there
    monkeypatch.setenv("CELLAR_ADDON_HOST", "s3.amazonaws.com")
    monkeypatch.setenv("CELLAR_ADDON_KEY_ID", "testing")
    monkeypatch.setenv("CELLAR_ADDON_KEY_SECRET", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    main._recent_presses.clear()
    with mock_aws(), TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def bare_client(monkeypatch):
    """The app with no add-on linked at all."""
    from herbarium import main

    for name in ("MYSQL_ADDON_URI", "CELLAR_ADDON_HOST", "CELLAR_ADDON_KEY_ID", "CELLAR_ADDON_KEY_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(main.app) as test_client:
        yield test_client
