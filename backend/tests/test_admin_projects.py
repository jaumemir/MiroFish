"""Tests per als endpoints d'administració de projectes."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop):
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


def _seed(in_memory_db):
    """Crea un usuari, projecte, graf i simulació de prova."""
    from backend.app.db import get_session
    from backend.app.models.db_models import UserModel, ProjectModel, GraphModel, SimulationModel
    from backend.app.services.auth_service import hash_password
    with get_session() as db:
        u = UserModel(id='u1', email='a@b.com', name='A', role='user', status='active',
                      password_hash=hash_password('x'))
        p = ProjectModel(id='p1', name='Test', status='created', user_id='u1')
        g = GraphModel(id='g1', project_id='p1', backend='zep', status='ready')
        s = SimulationModel(id='s1', project_id='p1', graph_id='g1', status='completed',
                            platform='twitter')
        db.add_all([u, p, g, s])
        db.commit()


def test_list_admin_projects_empty(client, in_memory_db):
    res = client.get('/api/admin/projects')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []
    assert data['total'] == 0


def test_list_admin_projects_with_data(client, in_memory_db):
    _seed(in_memory_db)
    res = client.get('/api/admin/projects')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['total'] == 1
    proj = data['data'][0]
    assert proj['project_id'] == 'p1'
    assert proj['owner_email'] == 'a@b.com'
    assert proj['simulation_count'] == 1


def test_get_admin_project_detail(client, in_memory_db):
    _seed(in_memory_db)
    res = client.get('/api/admin/projects/p1')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    d = data['data']
    assert d['project_id'] == 'p1'
    assert d['owner_email'] == 'a@b.com'
    assert len(d['graphs']) == 1
    assert d['graphs'][0]['graph_id'] == 'g1'
    assert len(d['simulations']) == 1
    assert d['simulations'][0]['simulation_id'] == 's1'


def test_get_admin_project_not_found(client, in_memory_db):
    res = client.get('/api/admin/projects/nonexistent')
    assert res.status_code == 404


def test_delete_admin_project(client, in_memory_db):
    _seed(in_memory_db)
    res = client.delete('/api/admin/projects/p1')
    assert res.status_code == 200
    assert res.get_json()['success'] is True
    res2 = client.get('/api/admin/projects/p1')
    assert res2.status_code == 404


def test_delete_admin_project_not_found(client, in_memory_db):
    res = client.delete('/api/admin/projects/ghost')
    assert res.status_code == 404


def test_delete_admin_simulation(client, in_memory_db):
    _seed(in_memory_db)
    res = client.delete('/api/admin/simulations/s1')
    assert res.status_code == 200
    assert res.get_json()['success'] is True
    res2 = client.get('/api/admin/projects/p1')
    assert res2.status_code == 200
    assert res2.get_json()['data']['simulations'] == []


def test_delete_admin_simulation_not_found(client, in_memory_db):
    res = client.delete('/api/admin/simulations/ghost')
    assert res.status_code == 404
