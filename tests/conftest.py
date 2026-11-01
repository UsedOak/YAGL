import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import db
from backend.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', Path(tmp_path) / 'test.sqlite3')
    with TestClient(app) as test_client:
        yield test_client
