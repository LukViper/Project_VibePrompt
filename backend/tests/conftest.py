import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["AUTH_SECRET"] = "test-auth-secret"

import pytest
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
