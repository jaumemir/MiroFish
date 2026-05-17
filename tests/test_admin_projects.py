import pytest
from backend.app import create_app

@pytest.fixture
def app():
    return create_app({'TESTING': True, 'DATABASE_URL': 'sqlite:///:memory:'})

@pytest.fixture
def client(app):
    return app.test_client()

def test_list_admin_projects_empty(client):
    res = client.get('/api/admin/projects')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []
    assert data['total'] == 0
