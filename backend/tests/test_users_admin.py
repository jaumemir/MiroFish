"""Tests per a l'API d'administració d'usuaris."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import select
from backend.app.models.db_models import UserModel, ProjectModel, GraphModel
from backend.app.db import get_session


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


def test_list_users_empty(client, in_memory_db):
    res = client.get('/api/users/')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []


def test_create_user_sends_invitation(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email:
        res = client.post('/api/users/', json={
            'email': 'newuser@example.com',
            'name': 'New User',
            'role': 'user'
        })
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['email'] == 'newuser@example.com'
    assert data['data']['status'] == 'pending'
    mock_email.assert_called_once()


def test_create_user_duplicate_email(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        client.post('/api/users/', json={'email': 'dup@example.com', 'name': 'D', 'role': 'user'})
        res = client.post('/api/users/', json={'email': 'dup@example.com', 'name': 'D2', 'role': 'user'})
    assert res.status_code == 409


def test_get_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'get@example.com', 'name': 'Get', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.get(f'/api/users/{user_id}')
    assert res.status_code == 200
    assert res.get_json()['data']['email'] == 'get@example.com'


def test_patch_user_role(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'patch@example.com', 'name': 'P', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.patch(f'/api/users/{user_id}', json={'role': 'admin'})
    assert res.status_code == 200
    assert res.get_json()['data']['role'] == 'admin'


def test_soft_delete_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'del@example.com', 'name': 'Del', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.delete(f'/api/users/{user_id}')
    assert res.status_code == 200
    get_res = client.get(f'/api/users/{user_id}')
    assert get_res.get_json()['data']['status'] == 'disabled'


def test_reinvite_pending_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email:
        create_res = client.post('/api/users/', json={'email': 'reinv@example.com', 'name': 'R', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email2:
        res = client.post(f'/api/users/{user_id}/reinvite')
    assert res.status_code == 200
    mock_email2.assert_called_once()


def test_purge_user_deletes_external_graphs(client, in_memory_db):
    """purge_user ha de cridar delete_graph per cada graph amb external_id."""
    # Crear usuari
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'purge@example.com', 'name': 'Purge', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    # Crear projecte i grafs directament a la BD
    with get_session() as db:
        proj = ProjectModel(id='proj-purge-1', name='Test', status='created', user_id=user_id)
        db.add(proj)
        db.flush()
        g1 = GraphModel(project_id='proj-purge-1', external_id='ext-graph-1', status='ready')
        g2 = GraphModel(project_id='proj-purge-1', external_id='ext-graph-2', status='ready')
        g3 = GraphModel(project_id='proj-purge-1', external_id=None, status='ready')  # sense external_id
        db.add_all([g1, g2, g3])
        db.commit()

    with patch('backend.app.api.users.GraphBuilderService') as MockBuilder:
        mock_instance = MockBuilder.return_value
        res = client.delete(f'/api/users/{user_id}/purge')

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # delete_graph ha de ser cridat exactament 2 vegades (els 2 amb external_id)
    assert mock_instance.delete_graph.call_count == 2
    called_ids = {call.args[0] for call in mock_instance.delete_graph.call_args_list}
    assert called_ids == {'ext-graph-1', 'ext-graph-2'}

    # Verificar que l'usuari ha estat esborrat de la BD
    with get_session() as db:
        gone = db.execute(select(UserModel).where(UserModel.id == user_id)).scalar_one_or_none()
    assert gone is None


def test_purge_user_continues_if_graph_delete_fails(client, in_memory_db):
    """Si delete_graph falla, l'usuari s'esborra igualment."""
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'failgraph@example.com', 'name': 'FailGraph', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    with get_session() as db:
        proj = ProjectModel(id='proj-fail-1', name='Fail', status='created', user_id=user_id)
        db.add(proj)
        db.flush()
        g = GraphModel(project_id='proj-fail-1', external_id='ext-fail-1', status='ready')
        db.add(g)
        db.commit()

    with patch('backend.app.api.users.GraphBuilderService') as MockBuilder:
        mock_instance = MockBuilder.return_value
        mock_instance.delete_graph.side_effect = Exception("Zep unavailable")
        res = client.delete(f'/api/users/{user_id}/purge')

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # Usuari ja no existeix a la BD
    with get_session() as db:
        user = db.execute(
            select(UserModel).where(UserModel.id == user_id)
        ).scalar_one_or_none()
    assert user is None


def test_enable_disabled_user(client, in_memory_db):
    """Un usuari disabled es pot reactivar via PATCH status: active."""
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'enable@example.com', 'name': 'Enable', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    # Desactivar primer
    client.delete(f'/api/users/{user_id}')
    get_res = client.get(f'/api/users/{user_id}')
    assert get_res.get_json()['data']['status'] == 'disabled'

    # Reactivar
    res = client.patch(f'/api/users/{user_id}', json={'status': 'active'})
    assert res.status_code == 200
    assert res.get_json()['data']['status'] == 'active'
