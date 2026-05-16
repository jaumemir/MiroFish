"""Tests d'integració per a l'endpoint GET /api/graph/project/:id/detail."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop_init_db(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop_init_db):
        from backend.app import create_app
        application = create_app()

    application.config['TESTING'] = True
    application.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def project(in_memory_db):
    from backend.app.models.db_models import ProjectModel
    from backend.app.db import get_session
    with get_session() as db:
        p = ProjectModel(
            name='Test Project',
            simulation_requirement='Test question',
            status='graph_completed',
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id


def test_project_detail_returns_aggregated_data(client, project):
    resp = client.get(f'/api/graph/project/{project}/detail')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'project' in data
    assert 'files' in data
    assert 'ontology' in data
    assert 'graph' in data
    assert 'simulations' in data


def test_project_detail_not_found(client):
    resp = client.get('/api/graph/project/nonexistent-id/detail')
    assert resp.status_code == 404
