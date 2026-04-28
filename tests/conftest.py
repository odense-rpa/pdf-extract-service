import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from pdf_extract.main import app

    return TestClient(app)
