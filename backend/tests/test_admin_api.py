"""Tests per a l'API d'administració."""
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


def test_get_config_empty(client, in_memory_db):
    res = client.get('/api/admin/config')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)


def test_patch_config(client, in_memory_db):
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.model_name', value='qwen-plus',
            value_type='string', group='llm',
            label='Model LLM', description='Nom del model LLM principal',
            is_secret=False
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.model_name': 'gpt-4o'})
    assert res.status_code == 200

    res2 = client.get('/api/admin/config')
    entries = res2.get_json()['data']
    entry = next(e for e in entries if e['key'] == 'llm.model_name')
    assert entry['value'] == 'gpt-4o'


def test_get_executions_empty(client, in_memory_db):
    res = client.get('/api/admin/executions')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []


def test_get_config_secret_hides_value(client, in_memory_db):
    """GET no retorna el valor de claus secretes; retorna has_value=True."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-secret-key',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.get('/api/admin/config')
    assert res.status_code == 200
    entries = res.get_json()['data']
    entry = next(e for e in entries if e['key'] == 'llm.api_key')
    assert entry['value'] is None
    assert entry['has_value'] is True


def test_get_config_secret_no_value(client, in_memory_db):
    """has_value=False quan la clau secreta no té valor."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.get('/api/admin/config')
    entry = next(e for e in res.get_json()['data'] if e['key'] == 'llm.api_key')
    assert entry['value'] is None
    assert entry['has_value'] is False


def test_patch_config_secret_empty_does_not_update(client, in_memory_db):
    """PATCH amb valor buit en clau secreta no modifica el valor actual."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-original',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.api_key': ''})
    assert res.status_code == 200

    with get_session() as db:
        entry = db.get(SystemConfigModel, 'llm.api_key')
        assert entry.value == 'sk-original'


def test_patch_config_secret_with_value_updates(client, in_memory_db):
    """PATCH amb valor no buit en clau secreta sí que actualitza."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-original',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.api_key': 'sk-new-key'})
    assert res.status_code == 200

    with get_session() as db:
        entry = db.get(SystemConfigModel, 'llm.api_key')
        assert entry.value == 'sk-new-key'
