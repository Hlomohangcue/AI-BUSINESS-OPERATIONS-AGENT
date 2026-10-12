import pytest


@pytest.fixture(autouse=True)
def isolate_workflow_database(tmp_path, monkeypatch):
    """Give every test its own temporary workflow database."""
    test_db_path = tmp_path / "workflow_actions_test.db"

    monkeypatch.setenv(
        "WORKFLOW_DB_PATH",
        str(test_db_path),
    )
