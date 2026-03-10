import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    for module_name in ("backend.main", "backend.models", "backend.database"):
        if module_name in sys.modules:
            del sys.modules[module_name]

    database = importlib.import_module("backend.database")
    models = importlib.import_module("backend.models")
    main = importlib.import_module("backend.main")

    return {"main": main, "models": models, "database": database}


@pytest.fixture
def client(app_module):
    return TestClient(app_module["main"].app)
